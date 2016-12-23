import os.path
import yaml

import dbt.project as project


def read_config(profiles_dir=None):
    if profiles_dir is None:
        profiles_dir = default_profiles_dir

    config = {}
    path = os.path.join(profiles_dir, 'profiles.yml')

    if os.path.isfile(path):
        with open(path, 'r') as f:
            m = yaml.safe_load(f)
            return m['config']

    return {}


def is_opted_out(profiles_dir):
    config = read_config(profiles_dir)

    if config is not None and config.get("send_anonymous_usage_stats") == False:
        return True

    return False
