"""Views for the node settings page."""
# -*- coding: utf-8 -*-
import datetime
from rest_framework import status as http_status
import os
import re
from lxml import etree
import logging

from flask import request
from flask import redirect

from framework.auth.decorators import must_be_logged_in
from framework.exceptions import HTTPError
from django.core.exceptions import ValidationError
from osf.models import ExternalAccount

from addons.base import generic_views
from addons.weko import client
from addons.weko.serializer import WEKOSerializer
from addons.weko import settings as weko_settings
from addons.weko.provider import REPOID_BASIC_AUTH, WEKOProvider
from osf.utils import permissions
from website.project.decorators import (
    must_have_addon, must_be_addon_authorizer,
    must_have_permission, must_not_be_registration,
    must_be_contributor_or_public,
)

from website.util import rubeus, api_url_for
from website.oauth.utils import get_service
from website.oauth.signals import oauth_complete

from admin.rdm_addons.decorators import must_be_rdm_addons_allowed

logger = logging.getLogger('addons.weko.views')

SHORT_NAME = 'weko'
FULL_NAME = 'WEKO'

@must_be_logged_in
@must_be_rdm_addons_allowed(SHORT_NAME)
def weko_oauth_connect(repoid, auth):
    service = get_service(SHORT_NAME)
    return redirect(service.get_repo_auth_url(repoid))

@must_be_logged_in
@must_be_rdm_addons_allowed(SHORT_NAME)
def weko_oauth_callback(repoid, auth):
    user = auth.user
    provider = get_service(SHORT_NAME)

    # Retrieve permanent credentials from provider
    if not provider.repo_auth_callback(user=user, repoid=repoid):
        return {}

    if provider.account and not user.external_accounts.filter(id=provider.account.id).exists():
        user.external_accounts.add(provider.account)
        user.save()

    oauth_complete.send(provider, account=provider.account, user=user)

    return {}


weko_account_list = generic_views.account_list(
    SHORT_NAME,
    WEKOSerializer
)

weko_import_auth = generic_views.import_auth(
    SHORT_NAME,
    WEKOSerializer
)

weko_deauthorize_node = generic_views.deauthorize_node(
    SHORT_NAME
)

weko_get_config = generic_views.get_config(
    SHORT_NAME,
    WEKOSerializer
)

## Auth ##

@must_be_logged_in
def weko_user_config_get(auth, **kwargs):
    """View for getting a JSON representation of the logged-in user's
    WEKO user settings.
    """

    user_addon = auth.user.get_addon('weko')
    user_has_auth = False
    if user_addon:
        user_has_auth = user_addon.has_auth

    return {
        'result': {
            'userHasAuth': user_has_auth,
            'urls': {
                'accounts': api_url_for('weko_account_list'),
            },
            'repositories': weko_settings.REPOSITORY_IDS
        },
    }, http_status.HTTP_200_OK


## Config ##

@must_not_be_registration
@must_have_addon(SHORT_NAME, 'user')
@must_have_addon(SHORT_NAME, 'node')
@must_be_addon_authorizer(SHORT_NAME)
@must_have_permission(permissions.WRITE)
def weko_set_config(node_addon, user_addon, auth, **kwargs):
    """Saves selected WEKO and Index to node settings"""

    user_settings = node_addon.user_settings
    user = auth.user

    if user_settings and user_settings.owner != user:
        raise HTTPError(http_status.HTTP_403_FORBIDDEN)

    index_id = request.json.get('index', {}).get('id')

    if index_id is None:
        return HTTPError(http_status.HTTP_400_BAD_REQUEST)

    connection = client.connect_from_settings(weko_settings, node_addon)
    index = client.get_index_by_id(connection, index_id)

    node_addon.set_folder(index, auth)

    return {'index': index.title}, http_status.HTTP_200_OK

@must_be_logged_in
@must_be_rdm_addons_allowed(SHORT_NAME)
def weko_add_user_account(auth, **kwargs):
    """Verifies new external account credentials and adds to user's list"""
    try:
        sword_url = request.json['sword_url']
        access_key = request.json['access_key']
        secret_key = request.json['secret_key']
    except KeyError:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST)

    if not (sword_url and access_key and secret_key):
        return {
            'message': 'All the fields above are required.'
        }, http_status.HTTP_400_BAD_REQUEST

    try:
        user_info = client.connect_or_error(sword_url,
                                            username=access_key,
                                            password=secret_key).get_login_user()
    except (HTTPError, IOError):
        logging.exception('Connection error')
        user_info = None
    if not user_info:
        return {
            'message': ('Unable to access account.\n'
                'Check to make sure that the above credentials are valid, '
                'and that they have permission to list indices.')
        }, http_status.HTTP_400_BAD_REQUEST

    provider = WEKOProvider(account=None, host=sword_url,
                            username=access_key, password=secret_key)
    try:
        provider.account.save()
    except ValidationError:
        # ... or get the old one
        provider.account = ExternalAccount.objects.get(
            provider=SHORT_NAME,
            provider_id='{}:{}:{}'.format(REPOID_BASIC_AUTH, sword_url,
                                          access_key).lower()
        )
        if provider.account.oauth_key != secret_key:
            provider.account.oauth_key = secret_key
            provider.account.save()
    assert provider.account is not None

    if not auth.user.external_accounts.filter(id=provider.account.id).exists():
        auth.user.external_accounts.add(provider.account)

    # Ensure WEKO is enabled.
    auth.user.get_or_add_addon('weko', auth=auth)
    auth.user.save()

    return {}

## Crud ##

@must_be_contributor_or_public
@must_have_addon(SHORT_NAME, 'node')
def weko_get_serviceitemtype(node_addon, **kwargs):
    connection = client.connect_from_settings_or_401(weko_settings, node_addon)
    return client.get_serviceitemtype(connection)

@must_be_contributor_or_public
@must_have_addon(SHORT_NAME, 'node')
def weko_get_item_view(itemid, node_addon, **kwargs):
    connection = client.connect_from_settings_or_401(weko_settings, node_addon)
    index_url = client.get_all_indices(connection)[0].about
    base_url = re.compile(r'^(.+)\?action=.*$').match(index_url).group(1)
    return {'url': '{}?action=repository_uri&item_id={}'.format(base_url, itemid)}, http_status.HTTP_200_OK

@must_have_permission('write')
@must_not_be_registration
@must_have_addon(SHORT_NAME, 'node')
def weko_add_item_created(node_addon, auth, **kwargs):
    parent_id = request.json.get('parent_id', None)
    item_id = request.json.get('item_id', None)
    title = request.json.get('title', None)

    node_addon.owner.add_log(
        action='weko_item_created',
        params={
            'project': parent_id,
            'node': item_id,
            'filename': title
        },
        auth=auth,
        log_date=datetime.datetime.utcnow(),
    )
    return {'status': 'added'}, http_status.HTTP_200_OK

@must_have_permission('write')
@must_not_be_registration
@must_have_addon(SHORT_NAME, 'node')
def weko_create_index(node_addon, auth, **kwargs):
    node = node_addon.owner

    now = datetime.datetime.utcnow()
    parent_index_id = request.json.get('parent_index', None)
    title_ja = request.json.get('title_ja', None)
    title_en = request.json.get('title_en', None)

    connection = client.connect_from_settings_or_401(weko_settings, node_addon)
    if parent_index_id is None:
        parent_index_id = node_addon.index_id

    index_id = client.create_index(connection, title_ja, title_en,
                                   parent_index_id)

    # Add a log
    node.add_log(
        action='weko_index_created',
        params={
            'project': node.parent_id,
            'node': node._id,
            'filename': title_ja
        },
        auth=auth,
        log_date=now,
    )

    indices = client.get_all_indices(connection)

    return {'nodeId': node._id,
            'name': title_ja,
            'kind': 'folder',
            'path': _get_path(indices, index_id),
            'provider': SHORT_NAME}, http_status.HTTP_200_OK

@must_have_permission('write')
@must_not_be_registration
@must_have_addon(SHORT_NAME, 'node')
def weko_generate_metadata(node_addon, auth, **kwargs):
    uploaded_filename = request.args.get('filename', None)
    uploaded_filenames = request.args.get('filenames', None)
    if uploaded_filename is None or uploaded_filenames is None:
        raise HTTPError(http_status.HTTP_400_BAD_REQUEST)
    uploaded_filenames = uploaded_filenames.split('\n')

    service_item_type = int(request.args.get('serviceItemType', None))
    connection = client.connect_from_settings_or_401(weko_settings, node_addon)
    item_types = client.get_serviceitemtype(connection)['item_type']
    internal_item_type_id = 10000 + service_item_type + 1

    item_type = item_types[service_item_type]
    title, ext = os.path.splitext(uploaded_filename)
    title_en = title

    contributors = []
    for contributor in node_addon.owner.contributors:
        contributors.append({'family': contributor.family_name,
                             'name': contributor.given_name})

    post_xml = client.create_import_xml(item_type,
                                        internal_item_type_id,
                                        uploaded_filenames,
                                        title, title_en,
                                        contributors)
    res = etree.tostring(post_xml, encoding='UTF-8', xml_declaration=True)
    return res, http_status.HTTP_200_OK

## HGRID ##

def _weko_root_folder(node_addon, auth, **kwargs):
    # Quit if no indices linked
    if not node_addon.complete:
        return []

    connection = client.connect_from_settings(weko_settings, node_addon)
    index = client.get_index_by_id(connection, node_addon.index_id)

    if index is None:
        return []

    return [rubeus.build_addon_root(
        node_addon,
        node_addon.index_title,
        permissions={'view': True, 'edit': True},
        private_key=kwargs.get('view_only', None),
    )]


@must_be_contributor_or_public
@must_have_addon(SHORT_NAME, 'node')
def weko_root_folder(node_addon, auth, **kwargs):
    return _weko_root_folder(node_addon, auth=auth)

def _get_path(indices, index_id):
    index = filter(lambda i: str(i.identifier) == str(index_id), indices)[0]
    if index.parentIdentifier is None:
        return '/weko:{}/'.format(index_id)
    else:
        return '{}weko:{}/'.format(_get_path(indices, index.parentIdentifier),
                              index_id)
