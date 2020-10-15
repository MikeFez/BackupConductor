import os
import hashlib

ENABLED = True
RUNNING_IN_DOCKER = os.getenv('RUNNING_IN_DOCKER', False)

class Project:
    """Project configuration"""
    ROOT = os.path.dirname(os.path.abspath(__file__).rsplit('/', 1)[0])
    
class Locations:
    CONFIG_FILE = "/config/config.yml"
    
if not RUNNING_IN_DOCKER:
    Locations.CONFIG_FILE = Project.ROOT + Locations.CONFIG_FILE
    
DEFAULT_CRONTAB_COMMENT = "Managed via BackupConductor"

CONFIG_CHECKSUM = None
DEFAULT_FREQUENCY = None
BACKUP_HOSTS = {}
TARGET_HOSTS = {}

def config_file_has_been_updated():
    global CONFIG_CHECKSUM
    latest_checksum = _get_config_checksum()
    if CONFIG_CHECKSUM is None or CONFIG_CHECKSUM != latest_checksum:
        CONFIG_CHECKSUM = latest_checksum
        return True
    return False

def _get_config_checksum():
    md5_hash = hashlib.md5()
    with open(Locations.CONFIG_FILE,"rb") as f:
        # Read and update hash in chunks of 4K
        for byte_block in iter(lambda: f.read(4096),b""):
            md5_hash.update(byte_block)
    return md5_hash.hexdigest()
