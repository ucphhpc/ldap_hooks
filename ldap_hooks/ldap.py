def add_dn(connection, dn, **kwargs):
    return connection.add(dn, **kwargs)


def modify_dn(connection, dn, changes, controls=None):
    return connection.modify(dn, changes, controls=None)


def search_for(connection, search_base, search_filter, **kwargs):
    return connection.search(search_base, search_filter, **kwargs)
