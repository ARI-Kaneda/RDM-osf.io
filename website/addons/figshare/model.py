# -*- coding: utf-8 -*-

import os

from modularodm import fields, Q
from framework.auth.decorators import Auth

from website.models import NodeLog
from website.addons.base import GuidFile
from website.addons.base import exceptions
from website.addons.base import AddonNodeSettingsBase, AddonUserSettingsBase

from .api import Figshare
from . import settings as figshare_settings
from . import messages


class FigShareGuidFile(GuidFile):

    article_id = fields.StringField(index=True)
    file_id = fields.StringField(index=True)

    @property
    def file_url(self):
        if self.article_id is None or self.file_id is None:
            raise ValueError('Path field must be defined.')
        return os.path.join(
            'figshare',
            'article',
            self.article_id,
            'file',
            self.file_id,
        )


class AddonFigShareUserSettings(AddonUserSettingsBase):

    oauth_request_token = fields.StringField()
    oauth_request_token_secret = fields.StringField()
    oauth_access_token = fields.StringField()
    oauth_access_token_secret = fields.StringField()

    @property
    def has_auth(self):
        return self.oauth_access_token is not None

    def to_json(self, user):
        rv = super(AddonFigShareUserSettings, self).to_json(user)
        rv.update({
            'authorized': self.has_auth,
        })
        return rv

    def remove_auth(self, save=False):
        self.oauth_access_token = None
        self.oauth_access_token_secret = None
        for node_settings in self.addonfigsharenodesettings__authorized:
            node_settings.deauthorize(auth=Auth(user=self.owner), save=True)
        if save:
            self.save()

    def delete(self, save=False):
        self.remove_auth(save=False)
        super(AddonFigShareUserSettings, self).delete(save=save)


class AddonFigShareNodeSettings(AddonNodeSettingsBase):

    figshare_id = fields.StringField()
    figshare_type = fields.StringField()
    figshare_title = fields.StringField()

    user_settings = fields.ForeignField(
        'addonfigshareusersettings', backref='authorized'
    )

    @property
    def embed_url(self):
        return 'http://wl.figshare.com/articles/{fid}/embed?show_title=1'.format(
            fid=self.figshare_id,
        )

    @property
    def api_url(self):
        if self.user_settings is None:
            return figshare_settings.API_URL
        else:
            return figshare_settings.API_OAUTH_URL

    @property
    def has_auth(self):
        return bool(self.user_settings and self.user_settings.has_auth)

    @property
    def linked_content(self):
        return {
            'id': self.figshare_id,
            'type': self.figshare_type,
            'title': self.figshare_title,
        }

    def authorize(self, user_settings, save=False):
        self.user_settings = user_settings
        node = self.owner
        node.add_log(
            action='figshare_node_authorized',
            params={
                'project': node.parent_id,
                'node': node._id,
            },
            auth=Auth(user=user_settings.owner),
        )
        if save:
            self.save()

    def deauthorize(self, auth=None, add_log=True, save=False):
        """Remove user authorization from this node and log the event."""
        self.user_settings = None
        self.figshare_id = None
        self.figshare_type = None
        self.figshare_title = None

        if add_log:
            node = self.owner
            self.owner.add_log(
                action='figshare_node_deauthorized',
                params={
                    'project': node.parent_id,
                    'node': node._id,
                },
                auth=auth,
            )

        if save:
            self.save()

    def serialize_waterbutler_credentials(self):
        if not self.has_auth:
            raise exceptions.AddonError('Cannot serialize credentials for unauthorized addon')
        return {
            'client_token': figshare_settings.CLIENT_ID,
            'client_secret': figshare_settings.CLIENT_SECRET,
            'owner_token': self.user_settings.oauth_access_token,
            'owner_secret': self.user_settings.oauth_access_token_secret,
        }

    def serialize_waterbutler_settings(self):
        if not self.figshare_type or not self.figshare_id:
            raise exceptions.AddonError('Cannot serialize settings for unconfigured addon')
        return {
            'container_type': self.figshare_type,
            'container_id': str(self.figshare_id),
        }

    def create_waterbutler_log(self, auth, action, metadata):
        if action in [NodeLog.FILE_ADDED, NodeLog.FILE_UPDATED]:
            name = metadata['name']
            article_id = metadata['extra']['articleId']
            file_id = metadata['extra']['fileId']
            urls = {
                'view': self.owner.web_url_for('figshare_view_file', aid=article_id, fid=file_id),
                'download': self.owner.api_url_for('figshare_download_file', aid=article_id, fid=file_id),
            }
        elif action == NodeLog.FILE_REMOVED:
            name = metadata['path']
            urls = {}
        self.owner.add_log(
            'figshare_{0}'.format(action),
            auth=auth,
            params={
                'project': self.owner.parent_id,
                'node': self.owner._id,
                'path': name,
                'urls': urls,
                'figshare': {
                    'id': self.figshare_id,
                    'type': self.figshare_type,
                },
            },
        )

    def get_waterbutler_render_url(self, **kwargs):
        article_id = kwargs['articleId']
        file_id = kwargs['fileId']
        return self.owner.web_url_for('figshare_view_file', aid=article_id, fid=file_id)

    def delete(self, save=False):
        super(AddonFigShareNodeSettings, self).delete(save=False)
        self.deauthorize(add_log=False, save=save)

    def update_fields(self, fields, node, auth):
        updated = False
        if fields.get('id'):
            updated = updated or (fields['id'] != self.figshare_id)
            self.figshare_id = fields['id']
        if fields.get('title'):
            updated = updated or (fields['title'] != self.figshare_title)
            self.figshare_title = fields['title']
        if fields.get('type'):
            updated = updated or (fields['type'] != self.figshare_type)
            self.figshare_type = fields['type']

        self.save()
        if updated:
            # Configure comments visibility
            files_id = FigShareGuidFile.find(Q('node', 'eq', self.owner)).get_keys()
            for fs_file_id in files_id:
                fs_file = FigShareGuidFile.load(fs_file_id)
                for comment in getattr(fs_file, 'comment_target', []):
                    comment.hide(save=True)

            if self.figshare_type == 'project':
                articles = Figshare.from_settings(self.user_settings).project(self, self.figshare_id)['articles']
            else:
                articles = Figshare.from_settings(self.user_settings).article(self, self.figshare_id)['items']
            if not self.figshare_id or not self.has_auth or not articles:
                return
            for article in articles:
                files = article.get('files', [])
                for fs_file in files:
                    file_id = str(fs_file['id'])
                    try:
                        guid = FigShareGuidFile.find_one(
                            Q('node', 'eq', self.owner) &
                            Q('article_id', 'eq', str(article['article_id'])) &
                            Q('file_id', 'eq', file_id)
                        )
                    except:
                        continue
                    for comment in getattr(guid, 'comment_target', []):
                        comment.show(save=True)

            # Add log
            node.add_log(
                action='figshare_content_linked',
                params={
                    'project': node.parent_id,
                    'node': node._id,
                    'figshare': {
                        'type': self.figshare_type,
                        'id': self.figshare_id,
                        'title': self.figshare_title,
                    },
                },
                auth=auth,
            )

    def to_json(self, user):
        rv = super(AddonFigShareNodeSettings, self).to_json(user)

        figshare_user = user.get_addon('figshare')

        rv.update({
            'figshare_id': self.figshare_id or '',
            'figshare_type': self.figshare_type or '',
            'figshare_title': self.figshare_title or '',
            'node_has_auth': self.has_auth,
            'user_has_auth': bool(figshare_user) and figshare_user.has_auth,
            'figshare_options': [],
            'is_registration': self.owner.is_registration,
        })
        if self.has_auth:
            rv.update({
                'authorized_user': self.user_settings.owner.fullname,
                'owner_url': self.user_settings.owner.url,
                'is_owner': user == self.user_settings.owner
            })

        return rv

    #############
    # Callbacks #
    #############

    def before_page_load(self, node, user):
        """

        :param Node node:
        :param User user:
        :return str: Alert message

        """
        if not self.figshare_id:
            return []
        figshare = node.get_addon('figshare')
        # Quit if no user authorization

        node_permissions = 'public' if node.is_public else 'private'

        if figshare.figshare_type == 'project':
            if node_permissions == 'private':
                message = messages.BEFORE_PAGE_LOAD_PRIVATE_NODE_MIXED_FS.format(category=node.project_or_component, project_id=figshare.figshare_id)
                return [message]
            else:
                message = messages.BEFORE_PAGE_LOAD_PUBLIC_NODE_MIXED_FS.format(category=node.project_or_component, project_id=figshare.figshare_id)

        connect = Figshare.from_settings(self.user_settings)
        article_is_public = connect.article_is_public(self.figshare_id)

        article_permissions = 'public' if article_is_public else 'private'

        if article_permissions != node_permissions:
            message = messages.BEFORE_PAGE_LOAD_PERM_MISMATCH.format(
                category=node.project_or_component,
                node_perm=node_permissions,
                figshare_perm=article_permissions,
                figshare_id=self.figshare_id,
            )
            if article_permissions == 'private' and node_permissions == 'public':
                message += messages.BEFORE_PAGE_LOAD_PUBLIC_NODE_PRIVATE_FS
            return [message]

    def before_remove_contributor(self, node, removed):
        """

        :param Node node:
        :param User removed:
        :return str: Alert message

        """
        if self.user_settings and self.user_settings.owner == removed:
            return messages.BEFORE_REMOVE_CONTRIBUTOR.format(
                category=node.project_or_component,
                user=removed.fullname,
            )

    def after_remove_contributor(self, node, removed):
        """

        :param Node node:
        :param User removed:
        :return str: Alert message

        """
        if self.user_settings and self.user_settings.owner == removed:

            # Delete OAuth tokens
            self.deauthorize(auth=None, add_log=False, save=False)
            self.user_settings = None
            self.save()

            return messages.AFTER_REMOVE_CONTRIBUTOR.format(
                user=removed.fullname,
                url=node.url,
                category=node.project_or_component
            )

    def before_fork(self, node, user):
        """

        :param Node node:
        :param User user:
        :return str: Alert message

        """
        if self.user_settings and self.user_settings.owner == user:
            return messages.BEFORE_FORK_OWNER.format(
                category=node.project_or_component,
            )
        return messages.BEFORE_FORK_NOT_OWNER.format(
            category=node.project_or_component,
        )

    def after_fork(self, node, fork, user, save=True):
        """

        :param Node node: Original node
        :param Node fork: Forked node
        :param User user: User creating fork
        :param bool save: Save settings after callback
        :return tuple: Tuple of cloned settings and alert message

        """
        clone, _ = super(AddonFigShareNodeSettings, self).after_fork(
            node, fork, user, save=False
        )

        # Copy authentication if authenticated by forking user
        if self.user_settings and self.user_settings.owner == user:
            clone.user_settings = self.user_settings
            message = messages.AFTER_FORK_OWNER.format(
                category=fork.project_or_component,
            )
        else:
            message = messages.AFTER_FORK_NOT_OWNER.format(
                category=fork.project_or_component,
                url=fork.url + 'settings/'
            )
            return AddonFigShareNodeSettings(), message

        if save:
            clone.save()

        return clone, message

    def before_make_public(self, node):
        return (
            'This {cat} is connected to a Figshare project. Files marked as '
            'private on Figshare <strong>will be visible to the public'
            '</strong>.'
        ).format(
            cat=node.project_or_component,
        )

    def after_delete(self, node, user):
        self.deauthorize(Auth(user=user), add_log=True, save=True)

    def before_register(self, node, user):
        if self.has_auth and self.figshare_id:
            return messages.BEFORE_REGISTER.format(
                category=node.project_or_component,
            )
