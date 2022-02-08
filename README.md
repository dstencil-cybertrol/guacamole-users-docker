# guacamole-users-docker
 Container to sync LDAP objects to mysql for use with Apache Guacamole.

## ToDo
- Create automated tests with CI/CD.

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

## Example Deployment With Kubernetes

```yaml
# Guacamole users configmap
apiVersion: v1
kind: ConfigMap
metadata:
  name: guacamole-users-configmap
  namespace: idmz
  annotations:
    reloader.stakater.com/match: "true"
data:
  manual-connections.yaml: |
    manual_connections:
      defaults:
        connection:
          protocol: 'rdp'
        parameters:
          console-audio: 'true'
          create-drive-path: 'true'
          drive-name: 'shared'
          drive-path: '/shared'
          enable-drive: 'true'
          enable-printing: 'true'
          ignore-cert: 'true'
          port: '3389'
          printer-name: 'RemotePrinter'
          security: 'nla'
          username: '${GUAC_USERNAME}'
          password: '${GUAC_PASSWORD}'
          domain: 'domain.com'
      connections:
       - defaults: true
         connection:
           connection_name: 'TEST-CONNECTION.domain.com - 192.168.1.160'
         parameters:
           hostname: '192.168.1.160'
    #parameters section and specific paramters are only required if they are not the defaults.
    # If manual connections are specified, permissions are required to be set for all manual connections.
    # List all ldap groups under the connection_name for each manual connection. Any user in the ldap group
    # will have permission to connect with the specific connection.
    manual_permissions:
      "Domain Users":
        - 'TEST-CONNECTION.domain.com - 192.168.1.160'
      ThisIsATestGroup:
        - 'TEST-CONNECTION.domain.com - 192.168.1.160'
  auto-connections.yaml: |
    connection:
      protocol: 'rdp'
    parameters: # Connection parameters are defined here under 'Configuring Connections': https://guacamole.apache.org/doc/gug/configuring-guacamole.html
      console-audio: 'true'
      create-drive-path: 'true'
      drive-name: 'shared'
      drive-path: '/shared'
      enable-drive: 'true'
      enable-printing: 'true'
      ignore-cert: 'true'
      port: '3389'
      printer-name: 'RemotePrinter'
      security: 'nla'
      username: '${GUAC_USERNAME}'
      password: '${GUAC_PASSWORD}'
      domain: 'domain.com'
---
# Guacamole users deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: guacamole-users-deployment
  namespace: idmz
  annotations:
    reloader.stakater.com/search: "true"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: guacamole-users
  template:
    metadata:
      labels:
        app: guacamole-users
    spec:
      restartPolicy: Always
      containers:
        - name: guacamole-users-container-name
          image: alphabet5/guacamole-users:dev
          imagePullPolicy: Always
          env:
            - name: MYSQL_USER
              valueFrom:
                secretKeyRef:
                  name: guacamole
                  key: mysql_username
            - name: MYSQL_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: guacamole
                  key: mysql_password
            - name: MYSQL_DATABASE
              valueFrom:
                secretKeyRef:
                  name: guacamole
                  key: mysql_database
            - name: MYSQL_HOSTNAME
              value: guac-mysql-service
            - name: CFG_AUTO_CONNECTION_DNS
              value: 'false'
            - name: CFG_AUTO_CONNECTION_DNS_RESOLVER
              value: '192.168.1.159'
            - name: GUAC_ADMIN_GROUPS
              value: 'GuacAdmins'
            - name: LDAP_COMPUTER_BASE_DN
              value: 'DC=domain,DC=com'
            - name: LDAP_COMPUTER_FILTER
              value: '(objectCategory=Computer)'
            - name: LDAP_GROUP_NAME_FROM_CONN_NAME_REGEX
              value: '(.*?)\..+'
            - name: LDAP_GROUP_NAME_MOD
              value: '{regex}'
            - name: REFRESH_SPEED
              value: '300'
            - name: MANUAL_ONLY
              value: 'false'
          volumeMounts:
            - name: guacamole-users-volume
              mountPath: "/configs/manual-connections.yaml"
              subPath: "manual-connections.yaml"
            - name: guacamole-users-volume
              mountPath: "/configs/auto-connections.yaml"
              subPath: "auto-connections.yaml"
            - name: guacamole-properties-volume
              mountPath: "/configs/guacamole.properties"
              subPath: "guacamole.properties"
      volumes:
        - name: guacamole-users-volume
          configMap:
            name: guacamole-users-configmap
        - name: guacamole-properties-volume
          configMap:
            name: guacamole-properties-configmap
```


## Changelog

### 0.0.1
- Changed the LDAP connection attempt to never timeout (timeout causes a crash if the ldap server is unavailable.)
- Changed the MySQL connection attempt to never timeout.
- Changed the kubernetes manifest in the readme to just be for guacamole-users-docker.

### 0.0.2
- Changed the guacamole.properties for the ldap connection to be overridden with environment variables. This allows for ldap-search-bind-password to be passed with LDAP_SEARCH_BIND_PASSWORD environment variable.

### 0.0.3
- Changed the order so that ldap_info is updated before checking / waiting for the ldap server. 