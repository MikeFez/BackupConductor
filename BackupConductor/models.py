import json
import yaml
import config

class Frequency:
    def __init__(self, population_data):
        self.hourly = False
        self.daily = False
        self.weekly = False
        self.monthly = False
        self.populate(population_data)
        
    def populate(self, population_data):
        _populate_from_dict(self, population_data)
        
class Host:
    def __init__(self):
        self.name = None
        self.ssh_host = None
        self.ssh_port = None
        self.ssh_user = None
    
class Directory:
    def __init__(self, population_data):
        self.name = None
        self.location = None
        self.backup_target = None
    
        # Non Essential
        self.frequency = None
        self.backup_subfolder = None
        self.perform_before = None
        self.perform_after = None
        self.populate(population_data)
        
    def populate(self, population_data):
        _populate_from_dict(self, population_data)
        if 'frequency' in population_data:
            self.frequency = Frequency(population_data.pop('frequency'))
        else:
            self.frequency = config.DEFAULT_FREQUENCY
    
class BackupHost(Host):
    def __init__(self, population_data):
        Host.__init__(self)
        self.directories = []
        self.populate(population_data)
        
    def populate(self, population_data):
        directories_dict = population_data.pop('directories')
        _populate_from_dict(self, population_data)
        for directory_data in directories_dict:
            self.directories.append(Directory(directory_data))

class TargetHost(Host):
    def __init__(self, population_data):
        Host.__init__(self)
        self.backup_directory = None
        self.populate(population_data)
        
    def populate(self, population_data):
        _populate_from_dict(self, population_data)

def _populate_from_dict(model, cfg_dict):
    valid_attrs = [i for i in model.__dict__.keys() if i[:1] != '_']
    
    for cfg_name, cfg_value in cfg_dict.items():
        if cfg_name in valid_attrs:
            setattr(model, cfg_name, cfg_value)
    return model

def validate():
    for hostname, host in config.BACKUP_HOSTS.items():
        for directory in host.directories:
            if directory.backup_target not in config.TARGET_HOSTS:
                raise ValueError(f"Invalid configuration for {hostname}: An entry for {directory.backup_target} does not exist as a target host")
    return

def pretty_print(data):
    print(json.dumps(data, sort_keys=True, indent=2))

def populate_from_config():
    with open(config.Locations.CONFIG_FILE, "r") as config_file:
        app_cfg = yaml.load(config_file, Loader=yaml.FullLoader)
    
    config.DEFAULT_FREQUENCY = Frequency(app_cfg['default_frequency'])
    
    for host_name, population_data in app_cfg['targets'].items():
        population_data['name'] = host_name
        config.TARGET_HOSTS[host_name] = TargetHost(population_data)
    
    for host_name, population_data in app_cfg['backup'].items():
        population_data['name'] = host_name
        config.BACKUP_HOSTS[host_name] = BackupHost(population_data)
        
    return