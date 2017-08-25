"""Class GaleraNodeSet implementation."""
from proxysql_tools.galera.exceptions import GaleraClusterNodeNotFound
from proxysql_tools.galera.galera_node import GaleraNode
from proxysql_tools.proxysql.backendset import BackendSet


class GaleraNodeSet(BackendSet):
    """Set for galera nodes"""

    def __contains__(self, item):
        if isinstance(item, GaleraNode):  # pylint: disable=duplicate-code
            return item in self._backend_list
        elif isinstance(item, GaleraNodeSet):
            for backend in item:
                if backend not in self:
                    return False
            return True

        return False

    def find(self, host=None, port=3306, state=None):
        """
        Find node by host and port

        :param host: Hostname of backend
        :param port: Port of backend
        :param state: State of node
        :return: Return found node
        :raises: GaleraClusterNodeNotFound
        """

        if host:
            needle = GaleraNode(host, port)
            for node in self._backend_list:
                if needle == node:
                    return node
            raise GaleraClusterNodeNotFound('Backend %s not found' % needle)

        if state:
            nodes = []
            for node in self._backend_list:
                if node.wsrep_local_state == state:
                    nodes.append(node)
            if nodes:
                return nodes
            raise GaleraClusterNodeNotFound('Nodes with state %d not found' % state)

    def remove(self, backend):
        """Remove node from the set

        :param backend: Node to remove.
        :type backend: GaleraNode
        :raise GaleraClusterNodeNotFound: if node is not in the set
        """
        try:
            self._backend_list.remove(backend)
        except ValueError as err:
            raise GaleraClusterNodeNotFound(err)