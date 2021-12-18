# guacamole-users-docker
 Container to sync LDAP objects to mysql for use with Apache Guacamole.

## ToDo
- Create automated tests with CI/CD.
- Add mysql initialization checks and execution to the startup. (maybe)

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
# MySQL ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: mysql-init-script-configmap
  namespace: idmz
  annotations:
    reloader.stakater.com/match: "true"
data:
  initdb.sh: |
    #!/bin/bash
    # Initialize MySQL database.
    # Add this into the container via mount point.
    # This should be in the same folder as the guacamole initdb.sql.script file.
    # This file is executed before initdb.sql.script as files are executed in alphabetical order.
    while ! mysqladmin -uroot -p$MYSQL_ROOT_PASSWORD ping -hlocalhost --silent; do
        sleep 1
    done
    sleep 1
    mysql -uroot -p$MYSQL_ROOT_PASSWORD --force -e "FLUSH PRIVILEGES;" || true
    # Not required since it's created by the entrypoint with the env. mysql -uroot -p$MYSQL_ROOT_PASSWORD --force -e "CREATE DATABASE $MYSQL_DATABASE;" || true
    # I don't think this is required? mysql -uroot -p$MYSQL_ROOT_PASSWORD --force -e "CREATE USER '$MYSQL_USER'@'%' IDENTIFIED WITH mysql_native_password BY '$MYSQL_PASSWORD';" || true
    mysql -uroot -p$MYSQL_ROOT_PASSWORD --force -e "GRANT SELECT,INSERT,UPDATE,DELETE ON $MYSQL_DATABASE.* TO '$MYSQL_USER'@'%';" || true
    mysql -uroot -p$MYSQL_ROOT_PASSWORD --force -e "FLUSH PRIVILEGES;" || true
    mysql -uroot -p$MYSQL_ROOT_PASSWORD --force $MYSQL_DATABASE < /mysqlinit/initdb.sql || true
    mysql -uroot -p$MYSQL_ROOT_PASSWORD --force -e "USE $MYSQL_DATABASE; SET @salt = UNHEX(SHA2(UUID(), 256));INSERT INTO guacamole_entity (name, type) VALUES ('guacadmin', 'USER') ON DUPLICATE KEY UPDATE name='guacadmin', type='USER';INSERT INTO guacamole_user (entity_id,password_salt,password_hash,password_date) SELECT entity_id,@salt,UNHEX(SHA2(CONCAT('$GUACADMIN_PASSWORD', HEX(@salt)), 256)),CURRENT_TIMESTAMP FROM guacamole_entity WHERE name = 'guacadmin' AND type = 'USER' ON DUPLICATE KEY UPDATE password_salt=@salt,password_hash=UNHEX(SHA2(CONCAT('$GUACADMIN_PASSWORD', HEX(@salt)), 256)),password_date=CURRENT_TIMESTAMP;" || true
---
# MySQL Service
apiVersion: v1
kind: Service
metadata:
  name: guac-mysql-service
  namespace: idmz
spec:
  ports:
    - protocol: TCP
      port: 3306
      targetPort: 3306
  selector:
    app: mysql
---
# MySQL Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mysql-deployment
  namespace: idmz
  annotations:
    reloader.stakater.com/search: "true"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mysql
  template:
    metadata:
      labels:
        app: mysql
    spec:
      restartPolicy: Always
      initContainers:
        - name: mysql-init-container
          image: guacamole/guacamole
          command:
            - '/bin/bash'
            - '-c'
            - '/opt/guacamole/bin/initdb.sh --mysql > /mysqlinit/initdb.sql'
          volumeMounts:
            - name: mysql-init-sql-script-volume
              mountPath: "/mysqlinit/"
      containers:
        - name: mysql-container-name
          image: mariadb
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
            - name: MYSQL_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: guacamole
                  key: mysql_root_password
            - name: GUACADMIN_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: guacamole
                  key: guacadmin_password
          ports:
            - name: mysql
              containerPort: 3306
          volumeMounts:
            - name: mysql-init-sql-script-volume
              mountPath: "/mysqlinit/"
            - name: mysql-init-script-volume
              mountPath: "/docker-entrypoint-initdb.d/initdb.sh"
              subPath: "initdb.sh"
          startupProbe:
            exec:
              command:
                - 'mysqladmin'
                - 'ping'
                - '-h'
                - 'localhost'
            failureThreshold: 60
            periodSeconds: 1
          readinessProbe:
            exec:
              command:
                - 'mysqladmin'
                - 'ping'
                - '-h'
                - 'localhost'
            initialDelaySeconds: 0
            periodSeconds: 1
          livenessProbe:
            exec:
              command:
                - 'mysqladmin'
                - 'ping'
                - '-h'
                - 'localhost'
            initialDelaySeconds: 0
            periodSeconds: 1
          resources:
            requests:
              memory: "64Mi"
              cpu: "250m"
            limits:
              memory: "128Mi"
              cpu: "500m"
      volumes:
        - name: mysql-init-script-volume
          configMap:
            name: mysql-init-script-configmap
        - name: mysql-init-sql-script-volume
          emptyDir: {}
        - name: guac-mysql-persistent-storage-volume
          persistentVolumeClaim:
            claimName: guac-mysql-persistent-storage
---
# Guacd service
apiVersion: v1
kind: Service
metadata:
  name: guacd-service
  namespace: idmz
spec:
  ports:
    - protocol: TCP
      port: 4822
      targetPort: 4822
  selector:
    app: guacd
---
# Guacd deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: guacd-deployment
  namespace: idmz
spec:
  replicas: 1
  selector:
    matchLabels:
      app: guacd
  template:
    metadata:
      labels:
        app: guacd
    spec:
      restartPolicy: Always
      containers:
        - name: guacd-container-name
          image: guacamole/guacd
          imagePullPolicy: Always
          ports:
            - containerPort: 4822
          startupProbe:
            tcpSocket:
              port: 4822
            failureThreshold: 45
            periodSeconds: 1
          readinessProbe:
            tcpSocket:
              port: 4822
            initialDelaySeconds: 0
            periodSeconds: 1
          livenessProbe:
            tcpSocket:
              port: 4822
            initialDelaySeconds: 0
            periodSeconds: 1
---
# Guacamole properties configmap
apiVersion: v1
kind: ConfigMap
metadata:
  name: guacamole-properties-configmap
  namespace: idmz
  annotations:
    reloader.stakater.com/match: "true"
data:
  guacamole.properties: |
    ldap-encryption-method: none
    ldap-group-base-dn: DC=domain,DC=com
    ldap-group-name-attribute: cn
    ldap-hostname: 192.168.1.159
    ldap-port: 389
    ldap-search-bind-dn: CN=guacuser,CN=Users,DC=domain,DC=com
    ldap-search-bind-password: Password_123$
    ldap-user-base-dn: CN=Users,DC=domain,DC=com
    ldap-user-search-filter: (objectCategory=*)
    ldap-username-attribute: samAccountName
---
# Guacamole logback.xml for more details in the logs.
apiVersion: v1
kind: ConfigMap
metadata:
  name: guacamole-logback-configmap
  namespace: idmz
  annotations:
    reloader.stakater.com/match: "true"
data:
  logback.xml: |
    <configuration>

        <!-- Appender for debugging -->
        <appender name="GUAC-DEBUG" class="ch.qos.logback.core.ConsoleAppender">
            <encoder>
                <pattern>%d{HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
            </encoder>
        </appender>

        <!-- Log at DEBUG level -->
        <root level="debug">
            <appender-ref ref="GUAC-DEBUG"/>
        </root>

    </configuration>
---
# Guacamole service
apiVersion: v1
kind: Service
metadata:
  name: guacamole-service
  namespace: idmz
spec:
  ports:
    - protocol: TCP
      port: 8080
      targetPort: 8080
  selector:
    app: guacamole
---
# Guacamole deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: guacamole-deployment
  namespace: idmz
  annotations:
    reloader.stakater.com/search: "true"
spec:
  replicas: 1
  selector:
    matchLabels:
      app: guacamole
  template:
    metadata:
      labels:
        app: guacamole
    spec:
      restartPolicy: Always
      containers:
        - name: guacamole-container-name
          image: guacamole/guacamole
          imagePullPolicy: Always
          command:
            - "/bin/bash"
            - "-c"
            - >
              sed -i 's#      </Host>#        <Valve className="org.apache.catalina.valves.RemoteIpValve"\n               internalProxies=".*"\n               remoteIpHeader="x-forwarded-for"\n               remoteIpProxiesHeader="x-forwarded-by"\n               protocolHeader="x-forwarded-proto" />\n      </Host>#g' /usr/local/tomcat/conf/server.xml; mkdir /etc/guacamole; mkdir /etc/guacamole/extensions; cp /opt/guacamole/ldap/guacamole-auth-ldap-*.jar /etc/guacamole/extensions; exec /opt/guacamole/bin/start.sh
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
            - name: GUACD_HOSTNAME
              value: guacd-service
            - name: MYSQL_HOSTNAME
              value: guac-mysql-service
            - name: GUACAMOLE_HOME
              value: /etc/guacamole
          ports:
            - name: guacamole
              containerPort: 8080
          volumeMounts:
            - name: guacamole-properties-volume
              mountPath: "/etc/guacamole/guacamole.properties"
              subPath: "guacamole.properties"
            - name: guacamole-logback-volume
              mountPath: "/etc/guacamole/logback.xml"
              subPath: "logback.xml"
          startupProbe:
            tcpSocket:
              port: 8080
            failureThreshold: 45
            periodSeconds: 1
          readinessProbe:
            tcpSocket:
              port: 8080
            initialDelaySeconds: 0
            periodSeconds: 1
          livenessProbe:
            tcpSocket:
              port: 8080
            initialDelaySeconds: 0
            periodSeconds: 1
      volumes:
        - name: guacamole-properties-volume
          configMap:
            name: guacamole-properties-configmap
        - name: guacamole-logback-volume
          configMap:
            name: guacamole-logback-configmap
---
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