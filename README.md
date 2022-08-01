# guacamole-users-docker
 Container to sync LDAP objects to mysql for use with Apache Guacamole.

## ToDo
- Create automated tests with CI/CD.
- Add addtional information to the readme.
- Pin versions with pip install.

## Build Instructions
```bash
docker stop guacamole-users
docker rm guacamole-users
docker image rm guacamole-users
docker build . --tag=guacamole-users
docker run -d --name guacamole-users \
  -e MYSQL_HOSTNAME=10.4.54.13 \
  -e MYSQL_USER=guacamole_user \
  -e MYSQL_PASSWORD=yourpassword \
  -e CFG_AUTO_CONNECTION_DNS_RESOLVER=10.4.105.101 \
  -e LDAP_GROUP_NAME_MOD='{regex}' \
  -v /yourpath:/configs guacamole-users
docker logs -f guacamole-users
```

## Changelog

### 0.0.6
- Added exception to log and continue when a connection permission is defined for a connection that doesn't exist.

### 0.0.5
- Added a check if admin groups is blank.
- Removed unnecessary default values from the Dockerfile.
- Changed to use dns by default for the auto connections.

### 0.0.4
- Changed the check for MANUAL_ONLY to be more explicit.
- Updated the logic for admin groups for the groups to be included.
- Include searching the ldap base for groups that are nested. This is to fix OU groups that have groups in the ldab base.
- Add debug printing.

### 0.0.3
- Changed the order so that ldap_info is updated before checking / waiting for the ldap server. 

### 0.0.2
- Changed the guacamole.properties for the ldap connection to be overridden with environment variables. This allows for ldap-search-bind-password to be passed with LDAP_SEARCH_BIND_PASSWORD environment variable.

### 0.0.1
- Changed the LDAP connection attempt to never timeout (timeout causes a crash if the ldap server is unavailable.)
- Changed the MySQL connection attempt to never timeout.
- Changed the kubernetes manifest in the readme to just be for guacamole-users-docker.
