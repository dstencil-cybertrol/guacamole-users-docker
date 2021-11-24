# guacamole-users-docker
 Container to sync LDAP objects to mysql for use with Apache Guacamole.

## ToDo
- Update Readme.
- Clean up examples.
- Test and generate kubernetes examples.
- Test with caddy rwp.
- Test and document ConfigMaps and GitOps CD.
- Move other config files to an example kubernetes configuration (haproxy, tomcat server.xml, etc.)
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

## The following sections were just notes taken during the initial testing. This has yet to be cleaned up.

## Environment Setup

```bash
#sudo snap install --classic kubectl
sudo snap install --classic microk8s
sudo usermod -a -G microk8s $USER
sudo chown -f -R $USER ~/.kube
newgrp microk8s

#Install podman - for testing
sudo apt-get install curl wget gnupg2 -y
sudo source /etc/os-release
sudo sh -c "echo 'deb http://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/xUbuntu_${VERSION_ID}/ /' > /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list"
sudo wget -nv https://download.opensuse.org/repositories/devel:kubic:libcontainers:stable/xUbuntu_${VERSION_ID}/Release.key -O- | sudo apt-key add -
sudo apt-get update -y
sudo apt-get -y install podman


```

Example guacamole.properties.
```text
ldap-encryption-method: none
ldap-group-base-dn: DC=domain,DC=com
ldap-group-name-attribute: cn
ldap-hostname: 10.4.105.101
ldap-port: 389
ldap-search-bind-dn: CN=guacuser,CN=Users,DC=domain,DC=com
ldap-search-bind-password: password
ldap-user-base-dn: CN=Users,DC=domain,DC=com
ldap-user-search-filter: (objectCategory=*)
ldap-username-attribute: samAccountName
```