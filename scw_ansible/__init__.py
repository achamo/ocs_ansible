import os
import json
import argparse
import sys
import re
from scaleway.apis import ComputeAPI
from ConfigParser import ConfigParser


class ScwServer(object):
    def __init__(self, api_url):
        self.api = ComputeAPI(
            auth_token=os.environ['SCW_TOKEN'],
            base_url=api_url)
        self.session = self.api.make_requests_session()

    def get_servers(self, uri="/servers"):
        response = self.session.request(
            "GET", "{base}{uri}".format(
                base=self.api.base_url,
                uri=uri
            )
        )
        for item in response.json()["servers"]:
            yield item
        if 'next' in response.links:
            for item in self.get_servers(response.links['next']['url']):
                yield item


class ScwAnsible(object):

    def __init__(self):
        args = self.parse_args()
        if 'SCW_REGION' in os.environ:
            region = os.environ['SCW_REGION']
        else:
            region = 'par1'
        host_folder = os.path.dirname(sys.argv[0])
        config_path = os.path.join(host_folder, "scaleway.cfg")
        config = None
        if os.path.exists(config_path):
            config = ConfigParser()
            config.read(config_path)

        hostgroups = {'_meta': {'hostvars': {}}}

        if args.host is not None:
            print(json.dumps({}))
        else:
            scw = ScwServer("https://cp-{}.scaleway.com".format(region))
            hostgroups = {'_meta': {'hostvars': {}}}
            for server in scw.get_servers():
                name = re.sub(r'[^a-z]', '-', server.get('name').lower())
                if server.get('state') != 'running':
                    continue
                var = {}
                environments = []
                for tag in server.get('tags'):
                    if tag.find(':') == -1:
                        environments.append("tag_%s" % tag)
                        continue
                    (key, value) = tag.split(':', 1)
                    if key == 'environment':
                        environments.append(value)
                    else:
                        var[key] = value
                if config is not None \
                        and config.has_option('defaults', 'environment') \
                        and config.get('defaults', 'environment') \
                        not in environments:
                    continue
                for env in environments:
                    if env not in hostgroups:
                        hostgroups[env] = {'hosts': []}
                    hostgroups[env]['hosts'].append(name)
                if server.get('public_ip', None) is None:
                    var['ansible_ssh_host'] = server['private_ip']
                else:
                    var['ansible_ssh_host'] = server['public_ip']['address']
                var['scw'] = server
                hostgroups['_meta']['hostvars'][name] = var

        if args.list:
            print(json.dumps(hostgroups))

        if args.cssh:
            for group, values in hostgroups.iteritems():
                if group == '_meta':
                    continue
                list_hosts = ["root@{0}".format(host)
                              for host in values['hosts']]
                print("{0} = {1}".format(group, " ".join(list_hosts)))

    def parse_args(self):
        parser = argparse.ArgumentParser(description="SCW inventory")
        parser.add_argument('--list', action='store_true')
        parser.add_argument('--cssh', action='store_true')
        parser.add_argument('--host')
        return parser.parse_args()


def main():
    ScwAnsible()
