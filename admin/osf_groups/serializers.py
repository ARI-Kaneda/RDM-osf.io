from guardian.shortcuts import get_perms
from osf.utils import permissions


def serialize_group(osf_group):

    return {
        'id': osf_group._id,
        'name': osf_group.name,
        'created': osf_group.created,
        'modified': osf_group.modified,
        'creator': serialize_members(osf_group.creator, osf_group),
        'managers': [serialize_members(manager, osf_group) for manager in osf_group.managers],
        'members': [serialize_members(member, osf_group) for member in osf_group.members_only],
        'nodes': [serialize_node_for_groups(node, osf_group) for node in osf_group.nodes]
    }

def serialize_node_for_groups(node, osf_group):
    return {
        'title': node.title,
        'id': node._id,
        'permission': permissions.reduce_permissions(get_perms(osf_group.member_group, node))
    }

def serialize_members(member, osf_group):
    """
    If unregistered, shows unclaimed record name associated with group member specifically
    """
    return {
        'name': member.fullname if member.is_registered else member.unclaimed_records[osf_group._id].get('name'),
        'id': member._id,
    }
