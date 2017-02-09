from proxysql_tools.entities.galera import (
    LOCAL_STATE_SYNCED, LOCAL_STATE_DONOR_DESYNCED
)
from proxysql_tools.managers.galera_manager import (
    GaleraManager, GaleraNodeNonPrimary, GaleraNodeUnknownState
)
from proxysql_tools.managers.proxysql_manager import ProxySQLManager


def register_cluster_with_proxysql(proxy_host, proxy_admin_port,
                                   proxy_admin_user, proxy_admin_pass,
                                   hostgroup_id_writer, hostgroup_id_reader,
                                   cluster_host, cluster_port, cluster_user,
                                   cluster_pass):
    """Register a Galera cluster within ProxySQL. The nodes in the cluster
    will be distributed between writer hostgroup and reader hostgroup.

    :param str proxy_host: The ProxySQL host.
    :param int proxy_admin_port: The ProxySQL admin port.
    :param str proxy_admin_user: The ProxySQL admin user.
    :param str proxy_admin_pass: The ProxySQL admin password.
    :param int hostgroup_id_writer: The ID of writer ProxySQL hostgroup.
    :param int hostgroup_id_reader: The ID of reader ProxySQL hostgroup.
    :param str cluster_host: Hostname of a node in Galera cluster.
    :param int cluster_port: Port of a node in Galera cluster.
    :param str cluster_user: MySQL username of a user in Galera cluster.
    :param str cluster_pass: MySQL password of a user in Galera cluster.
    :return bool: Returns True on success, False otherwise.
    """
    # We also check that the initial node that is being used to register the
    # cluster with ProxySQL is actually a healthy node and part of the primary
    # component.
    galera_man = GaleraManager(cluster_host, cluster_port,
                               cluster_user, cluster_pass)
    try:
        galera_man.discover_cluster_nodes()
    except GaleraNodeNonPrimary:
        return False
    except GaleraNodeUnknownState:
        return False

    # First we try to find nodes in synced state.
    galera_nodes_synced = filter_nodes_with_state(galera_man.nodes,
                                                  LOCAL_STATE_SYNCED)
    galera_nodes_desynced = filter_nodes_with_state(galera_man.nodes,
                                                    LOCAL_STATE_DONOR_DESYNCED)

    # If we found no nodes in synced or donor/desynced state then we
    # cannot continue.
    if not galera_nodes_synced and not galera_nodes_desynced:
        return False

    proxysql_man = ProxySQLManager(proxy_host, proxy_admin_port,
                                   proxy_admin_user, proxy_admin_pass)

    for hostgroup_id in [hostgroup_id_writer, hostgroup_id_reader]:
        # Let's remove all the nodes defined in the hostgroups that are not
        # part of this cluster or are not in desired state.
        desired_state = LOCAL_STATE_SYNCED if galera_nodes_synced else \
            LOCAL_STATE_DONOR_DESYNCED

        backends_list = deregister_unhealthy_backends(
            proxysql_man, galera_man.nodes, hostgroup_id, [desired_state])

        # If there are more than one nodes in the writer hostgroup then we
        # remove all but one.
        if len(backends_list) > 1 and hostgroup_id == hostgroup_id_writer:
            for backend in backends_list[1:]:
                proxysql_man.deregister_mysql_backend(hostgroup_id_writer,
                                                      backend.hostname,
                                                      backend.port)

        if len(backends_list) == 0:
            # If there are no backends registered in the writer hostgroup then
            # we register one healthy galera node.
            if hostgroup_id == hostgroup_id_writer:
                node = galera_nodes_synced[0] if galera_nodes_synced else \
                    galera_nodes_desynced[0]
                proxysql_man.register_mysql_backend(hostgroup_id_writer,
                                                    node.host, node.port)

            # If there are no backends registered in the reader hostgroup then
            # we register all of the healthy galera nodes.
            if hostgroup_id == hostgroup_id_reader:
                nodes_list = galera_nodes_synced if galera_nodes_synced else \
                    galera_nodes_desynced
                for node in nodes_list:
                    proxysql_man.register_mysql_backend(hostgroup_id_reader,
                                                        node.host, node.port)

    # Now filter nodes that are common between writer hostgroup and reader
    # hostgroup
    writer_backends = proxysql_man.fetch_mysql_backends(hostgroup_id_writer)
    reader_backends = proxysql_man.fetch_mysql_backends(hostgroup_id_reader)

    # If we have more than one backend registered in the reader hostgroup
    # then we remove the ones that are also present in the writer hostgroup
    if len(reader_backends) > 1:
        for backend in set(writer_backends).intersection(set(reader_backends)):
            proxysql_man.deregister_mysql_backend(hostgroup_id_reader,
                                                  backend.hostname,
                                                  backend.port)

    return True


def deregister_unhealthy_backends(proxysql_man, galera_nodes, hostgroup_id,
                                  desired_states):
    """Remove backends in a particular hostgroup that are not in the Galera
    cluster or whose state is not in one of the desired states.

    :param ProxySQLManager proxysql_man: ProxySQL manager corresponding to the
        ProxySQL instance.
    :param list[GaleraNode] galera_nodes: List of Galera nodes.
    :param int hostgroup_id: The ID of the ProxySQL hostgroup.
    :param list[str] desired_states: Nodes not in this list of states are
        considered unhealthy.
    :return list[GaleraNode]: List of backends that correspond to the Galera
        nodes that are part of the cluster.
    """
    backend_list = proxysql_man.fetch_mysql_backends(hostgroup_id)
    for backend in backend_list:
        # Find the matching galera node and then see if the node state is
        # synced or donor/desynced. If not one of those two states then we
        # deregister the node from ProxySQL as well.
        for node in galera_nodes:
            if node.host == backend.hostname and node.port == backend.port:
                if node.local_state in desired_states:
                    continue

        proxysql_man.deregister_mysql_backend(hostgroup_id, backend.hostname,
                                              backend.port)

        # Remove the backend from list of writer backends as well.
        backend_list.remove(backend)

    return backend_list


def filter_nodes_with_state(galera_nodes, desired_state):
    """Given a list of Galera Nodes, return the node that is in the desired
    state.

    :param list[GaleraNode] galera_nodes: List of Galera nodes.
    :param str desired_state: Find a node with this state.
    :return GaleraNode: Return a node in desired state.
    """
    nodes = []
    for node in galera_nodes:
        if node.local_state == desired_state:
            nodes.append(node)

    return nodes


def register_mysql_users_with_proxysql():
    pass
