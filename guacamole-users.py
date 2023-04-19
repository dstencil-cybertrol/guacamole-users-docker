import os
import sqlalchemy
from sqlalchemy.dialects.mysql import insert

# from sqlalchemy.sql import text
from time import sleep
import pymysql
from ldap3 import Server, Connection, ALL, SUBTREE
import yaml

# import hashlib
# from datetime import datetime
# import uuid
from rich.console import Console
from rich.traceback import install
from rich import print
import json
from copy import deepcopy
from collections import defaultdict
import re

# import threading
import dns.resolver


def dprint(input_obj):
    if os.environ["DEBUG"].lower() in ["t", "true", "y", "yes"]:
        console.print(input_obj)


def sql_insert(engine, conn, table, **kwargs):
    metadata = sqlalchemy.MetaData()
    table_obj = sqlalchemy.Table(table, metadata, autoload=True, autoload_with=engine)
    insert_statement = insert(table_obj).values(**kwargs)
    on_duplicate = insert_statement.on_duplicate_key_update(**kwargs)
    return conn.execute(on_duplicate)


# def pymysql_insert(connection, table, **kwargs):
#     # # Connect to SQL
#     # engine = sqlalchemy.create_engine('mysql+pymysql://' +
#     #                                   os.environ['MYSQL_USER'] + ':' +
#     #                                   os.environ['MYSQL_PASSWORD'] + '@' +
#     #                                   os.environ['MYSQL_HOSTNAME'] + ':3306/' +
#     #                                   os.environ['MYSQL_DATABASE'])
#     with connection.cursor() as cursor:
#         keys = ','.join(kwargs.keys())
#         values = ','.join(kwargs.values())
#         sql = f"INSERT INTO {table} ({keys}) VALUES ({values}) ON DUPLICATE KEY UPDATE "

def wait_for_sql(engine):
    delay = 1
    max_delay = 30
    while True:
        try:
            with engine.begin() as sql_conn:
                sql_conn.execute("SELECT 1")
                print("Connected to MySQL database")
                return True
        except sqlalchemy.exc.OperationalError as e:
            print(f"Failed to connect to MySQL database: {e}. Retrying in {delay} seconds...")

def wait_for_ldap(ldap_info):
    print_traceback = True
    while True:
        try:
            server = Server(ldap_info["ldap-hostname"], get_info=ALL)
            ldap_conn = Connection(
                server=server,
                user=ldap_info["ldap-search-bind-dn"],
                password=ldap_info["ldap-search-bind-password"],
                auto_bind=True,
            )
            return True
        except:
            if print_traceback:
                console.print_exception(show_locals=True)
                print_traceback = False
            print("Cannot connect to ldap server. Waiting...")
            sleep(1)


def get_mysql():
    # Connect to SQL
    engine = sqlalchemy.create_engine(
        "mysql+pymysql://"
        + os.environ["MYSQL_USER"]
        + ":"
        + os.environ["MYSQL_PASSWORD"]
        + "@"
        + os.environ["MYSQL_HOSTNAME"]
        + ":3306/"
        + os.environ["MYSQL_DATABASE"]
    )
    if not wait_for_sql(engine):
        return False
    return engine


def get_ldap():
    # Connect to LDAP
    ldap_info = yaml.load(open("/configs/guacamole.properties", "r"), yaml.FullLoader)
    # Loop through environment variables to allow guacamole.properties values to be overriden by the env.
    for k, v in os.environ.items():
        ldap_info[k.lower().replace("_", "-")] = v
    if not wait_for_ldap(ldap_info):
        return False
    # Fetch LDAP information
    server = Server(ldap_info["ldap-hostname"], get_info=ALL)
    ldap_conn = Connection(
        server=server,
        user=ldap_info["ldap-search-bind-dn"],
        password=ldap_info["ldap-search-bind-password"],
        auto_bind=True,
    )
    return ldap_conn, ldap_info


def update_connections():
    if os.environ["MANUAL_ONLY"].lower() not in ["true", "yes", "t", "y"]:
        ldap_conn, ldap_info = get_ldap()

        ldap_conn.search(
            search_base=os.environ["LDAP_BASE_DN"],
            search_scope=SUBTREE,
            search_filter=os.environ["LDAP_COMPUTER_FILTER"],
            attributes=["cn", "dNSHostName"],
        )
        ldap_computers = json.loads(ldap_conn.response_to_json())
        dprint("ldap_computers")
        dprint(ldap_computers)
        auto_conn_parameters = yaml.load(
            open("/configs/auto-connections.yaml", "r"), yaml.FullLoader
        )
    engine = get_mysql()
    # Create connections
    # computer_cn = dict()
    with engine.begin() as sql_conn:
        connections = list()
        connection_ids = list()
        # name_cn_id = defaultdict(lambda: {})
        if os.environ["MANUAL_ONLY"].lower() in ["false", "no", "f", "n"]:
            for computer in ldap_computers["entries"]:
                auto_conn_dns = os.environ["CFG_AUTO_CONNECTION_DNS"]
                if auto_conn_dns in ["true", "t", "y", "yes"]:
                    hostname = computer["attributes"]["dNSHostName"]
                    conn_name = hostname
                else:
                    dns.resolver.default_resolver = dns.resolver.Resolver(
                        configure=False
                    )
                    dns.resolver.default_resolver.nameservers = [
                        os.environ["CFG_AUTO_CONNECTION_DNS_RESOLVER"]
                    ]
                    hostname = (
                        dns.resolver.resolve(computer["attributes"]["dNSHostName"], "a")
                        .response.answer[0][0]
                        .address
                    )
                    conn_name = computer["attributes"]["dNSHostName"] + " - " + hostname
                connection = auto_conn_parameters
                connection["connection"]["connection_name"] = conn_name
                connection["parameters"]["hostname"] = hostname
                connections.append(deepcopy(connection))
                # name_cn_id[conn_name]['cn'] = computer['attributes']['cn']
        if os.path.isfile("/configs/manual-connections.yaml"):
            manual_connections = yaml.load(
                open("/configs/manual-connections.yaml", "r"), yaml.FullLoader
            )
            defaults = manual_connections["manual_connections"]["defaults"]
            for connection in manual_connections["manual_connections"]["connections"]:
                new_connection = dict()
                if connection["defaults"]:
                    new_connection["connection"] = (
                        defaults["connection"] | connection["connection"]
                    )
                    new_connection["parameters"] = (
                        defaults["parameters"] | connection["parameters"]
                    )
                else:
                    new_connection["connection"] = connection["connection"]
                    new_connection["parameters"] = connection["parameters"]
                connections.append(deepcopy(new_connection))

        for connection in connections:
            sql_insert(
                engine, sql_conn, "guacamole_connection", **connection["connection"]
            )
            conn_name = connection["connection"]["connection_name"]
            connection_id = sql_conn.execute(
                'SELECT connection_id from guacamole_connection WHERE connection_name = "'
                + conn_name
                + '";'
            ).fetchone()["connection_id"]
            # name_cn_id[connection['connection']['connection_name']]['id'] = connection_id
            connection_ids.append(connection_id)
            for parameter_name, parameter_value in connection["parameters"].items():
                sql_insert(
                    engine,
                    sql_conn,
                    "guacamole_connection_parameter",
                    connection_id=connection_id,
                    parameter_name=parameter_name,
                    parameter_value=parameter_value,
                )
            # Remove undefined parameters.
            sql_conn.execute(
                "DELETE FROM guacamole_connection_parameter WHERE connection_id = "
                + str(connection_id)
                + " AND parameter_name NOT IN ('"
                + "','".join(connection["parameters"].keys())
                + "');"
            )

        # Clean up undefined connections.
        connections = sql_conn.execute("SELECT * from guacamole_connection;").fetchall()
        for connection in connections:
            if connection["connection_id"] not in connection_ids:
                sql_conn.execute(
                    "DELETE from guacamole_connection WHERE connection_id = "
                    + str(connection["connection_id"])
                    + ";"
                )
                sql_conn.execute(
                    "DELETE from guacamole_connection_parameter WHERE connection_id = "
                    + str(connection["connection_id"])
                    + ";"
                )


def update_users():
    if os.environ["MANUAL_ONLY"].lower() in ["false", "no", "f", "n"]:
        ldap_conn, ldap_info = get_ldap()
        # Create list of LDAP Groups that contain all sub-groups.
        ldap_conn.search(
            search_base=ldap_info["ldap-group-base-dn"],
            search_scope=SUBTREE,
            search_filter="(objectCategory=Group)",
            attributes=["cn", "memberOf"],
        )
        ldap_entries = json.loads(ldap_conn.response_to_json())
        dprint("ldap_entries")
        dprint(ldap_entries)
        # Also search the base DN for groups. This is required as if the ldap-group-base-dn is an OU, it won't list out members of the group that are in the base DN.
        ldap_conn.search(
            search_base=os.environ["LDAP_BASE_DN"],
            search_scope=SUBTREE,
            search_filter="(objectCategory=Group)",
            attributes=["cn", "memberOf"],
        )
        ldap_entries_base = json.loads(ldap_conn.response_to_json())
        dprint("ldap_entries_base")
        dprint(ldap_entries_base)
        groups_cn = dict()
        for group in ldap_entries_base["entries"]:
            groups_cn[group["dn"]] = group["attributes"]["cn"]
        for group in ldap_entries["entries"]:
            groups_cn[group["dn"]] = group["attributes"]["cn"]
    # List parent groups. admin + manual + regex
    # Add conn id's for parent groups. admin + manual + regex
    engine = get_mysql()
    parent_groups = defaultdict(lambda: [])
    conn_ids = dict()
    with engine.begin() as sql_conn:
        for conn in sql_conn.execute("SELECT * FROM guacamole_connection;").fetchall():
            conn_ids[conn["connection_name"]] = conn["connection_id"]
    # Add the groups from the manually defined connections.
    if os.path.isfile("/configs/manual-connections.yaml"):
        manual_connections = yaml.load(
            open("/configs/manual-connections.yaml", "r"), yaml.FullLoader
        )
        for group in manual_connections["manual_permissions"]:
            for conn_name in manual_connections["manual_permissions"][group]:
                # This is appending the connection id for each named connection in the manual_permissions section.
                try:
                    parent_groups[group].append(conn_ids[conn_name])
                except KeyError:
                    console.print(
                        "Error: Group permission defined for connection '"
                        + conn_name
                        + "' in group '"
                        + group
                        + "' but there is no connection with that name."
                    )
    if os.environ["MANUAL_ONLY"].lower() in ["false", "no", "f", "n"]:
        # Add the groups from the regular expression defining the group name from the connection name.
        nested_groups = defaultdict(lambda: [])
        for conn_name, conn_id in conn_ids.items():
            regex_result = re.match(
                os.environ["LDAP_GROUP_NAME_FROM_CONN_NAME_REGEX"], conn_name
            ).group(1)
            if regex_result is not None:
                group_name = os.environ["LDAP_GROUP_NAME_MOD"].replace(
                    "{regex}", regex_result
                )
                for group in ldap_entries["entries"]:
                    if group["attributes"]["cn"] == group_name:
                        parent_groups[group_name].append(conn_id)
                        nested_groups[group_name].append(group["dn"])
                        break
        dprint("parent_groups")
        dprint(parent_groups)
        for i in range(4):
            for group_name, dn_list in nested_groups.items():
                for group in ldap_entries["entries"]:
                    for member_of in group["attributes"]["memberOf"]:
                        if member_of in dn_list:
                            nested_groups[group_name].append(group["dn"])
                if ldap_info["ldap-group-base-dn"] != os.environ["LDAP_BASE_DN"]:
                    for group in ldap_entries_base["entries"]:
                        for member_of in dn_list:
                            if member_of in group["attributes"]["memberOf"]:
                                nested_groups[group_name].append(group["dn"])
        dprint("nested_groups")
        dprint(nested_groups)

        for group, dn_list in nested_groups.items():
            for dn in dn_list:
                parent_groups[groups_cn[dn]] += parent_groups[group]

    group_permissions = dict()
    for group_name, ids in parent_groups.items():
        group_permissions[group_name] = list(set(ids))

    admin_groups = os.environ["GUAC_ADMIN_GROUPS"].split(",")
    for admin_group in admin_groups:
        if admin_group != "":
            group_permissions[admin_group] = list(set(conn_ids.values()))

    # Add groups and assign permissions.
    with engine.begin() as sql_conn:
        for group, conn_ids in group_permissions.items():
            sql_insert(
                engine,
                sql_conn,
                "guacamole_entity",
                **{"name": group, "type": "USER_GROUP"}
            )

            entity_id = sql_conn.execute(
                'SELECT entity_id from guacamole_entity WHERE name = "' + group + '";'
            ).fetchone()["entity_id"]
            sql_insert(
                engine,
                sql_conn,
                "guacamole_user_group",
                **{"entity_id": entity_id, "disabled": 0}
            )
            if len(conn_ids) > 1:
                sql_conn.execute(
                    "DELETE FROM guacamole_connection_permission WHERE entity_id = "
                    + str(entity_id)
                    + " AND connection_id NOT IN ("
                    + ",".join([str(i) for i in conn_ids])
                    + ");"
                )
            elif len(conn_ids) == 1:
                sql_conn.execute(
                    "DELETE FROM guacamole_connection_permission WHERE entity_id = "
                    + str(entity_id)
                    + " AND connection_id = "
                    + str(conn_ids[0])
                    + ";"
                )
            if group in os.environ["GUAC_ADMIN_GROUPS"].split(","):
                for permission in [
                    "CREATE_CONNECTION",
                    "CREATE_CONNECTION_GROUP",
                    "CREATE_SHARING_PROFILE",
                    "CREATE_USER",
                    "CREATE_USER_GROUP",
                    "ADMINISTER",
                ]:
                    sql_insert(
                        engine,
                        sql_conn,
                        "guacamole_system_permission",
                        **{"entity_id": entity_id, "permission": permission}
                    )
            for conn_id in conn_ids:
                if group not in os.environ["GUAC_ADMIN_GROUPS"].split(","):
                    permissions = ["READ"]
                else:
                    permissions = ["READ", "UPDATE", "DELETE", "ADMINISTER"]
                for permission in permissions:
                    sql_insert(
                        engine,
                        sql_conn,
                        "guacamole_connection_permission",
                        **{
                            "entity_id": entity_id,
                            "connection_id": conn_id,
                            "permission": permission,
                        }
                    )


if __name__ == "__main__":
    # Install rich traceback for better diagnostics.
    console = Console()
    if os.environ["DEBUG"].lower() in ["f", "false", "n", "no"]:
        show_locals = False
    else:
        show_locals = True
    install(show_locals=show_locals)
    from time import sleep

    while True:
        try:
            update_connections()
            update_users()
        except pymysql.err.OperationalError:
            console.print_exception(max_frames=1)
            console.print("Unable to connect to sql. Please check if sql is available.")
        except:
            console.print_exception()
        sleep(int(os.environ["REFRESH_SPEED"]))
