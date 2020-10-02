import config
import models
from time import sleep
from crontab import CronTab
import os
from loguru import logger
import paramiko

if config.RUNNING_IN_DOCKER:
    cron = CronTab(user=True)
ssh = paramiko.SSHClient()
ssh.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

def set_jobs():
    if config.RUNNING_IN_DOCKER:
        logger.info("Removing existing BackupConductor cron tasks")
        cron.remove_all(comment=config.DEFAULT_CRONTAB_COMMENT)
    for backup_host in config.BACKUP_HOSTS.values():
        for directory_data in backup_host.directories:
            set_schedule(backup_host, directory_data)
    return

def set_schedule(backup_host, directory_data):
    """Generate the crontab schedule"""
    logger.info(f"Configuring backups for {backup_host.name}::{directory_data.name}")
    if config.RUNNING_IN_DOCKER:
        if directory_data.frequency.hourly:
            job = cron.new(command=_get_job_cmd(backup_host, directory_data, 'hourly'), comment=config.DEFAULT_CRONTAB_COMMENT)
            job.hour.every(1)
            cron.write()
        if directory_data.frequency.daily:
            job = cron.new(command=_get_job_cmd(backup_host, directory_data, 'daily'), comment=config.DEFAULT_CRONTAB_COMMENT)
            job.every().dom()
            cron.write()
        if directory_data.frequency.weekly:
            job = cron.new(command=_get_job_cmd(backup_host, directory_data, 'weekly'), comment=config.DEFAULT_CRONTAB_COMMENT)
            job.dow.on('SUN')
            cron.write()
        if directory_data.frequency.monthly:
            job = cron.new(command=_get_job_cmd(backup_host, directory_data, 'monthly'), comment=config.DEFAULT_CRONTAB_COMMENT)
            job.every().month()
            cron.write()
    return


def get_frequencies_as_list(directory_data):
    return [freq_name.lower() for freq_name, freq_val in vars(directory_data.frequency).items() if freq_val is True]

def _ensure_backup_folders_exist():
    """Generate backup folders on target"""
    folders_per_host = {}
    for backup_host in config.BACKUP_HOSTS.values():
        for directory_data in backup_host.directories:
            frequencies = get_frequencies_as_list(directory_data)
            target_host = config.TARGET_HOSTS[directory_data.backup_target]
            if target_host not in folders_per_host:
                folders_per_host[target_host] = []
            for frequency in frequencies:
                folders_per_host[target_host].append(f'{target_host.backup_directory}/BackupConductor/{backup_host.name}/{directory_data.name}/{frequency}')
            
    for target_host, directories in folders_per_host.items():
        directory_creation_cmd = 'mkdir -p {' + ','.join(directories) + '}'
        logger.info(f'Creating directories: {directory_creation_cmd}')
        
        if config.RUNNING_IN_DOCKER:
            ssh = get_ssh_connection(target_host)
            (stdin, stdout, stderr) = ssh.exec_command(directory_creation_cmd)
            ssh.close()
    

def _get_job_cmd(backup_host, directory_data, frequency):
    target_host = config.TARGET_HOSTS[directory_data.backup_target]
    return f'ssh -Te none -p {backup_host.ssh_port} {backup_host.ssh_user}@{backup_host.ssh_host} "tar -C / -cz {directory_data.location}" | ssh -p {target_host.ssh_port} {target_host.ssh_user}@{target_host.ssh_host}  "cat > {target_host.backup_directory}/BackupConductor/{backup_host.name}/{directory_data.name}/{frequency}/$(date \'+%Y-%m-%d_%H-%M-%S\').tar.gz"'

def get_ssh_connection(host):
    ssh.connect(host.ssh_host, host.ssh_port, host.ssh_user)  # TODO: Support passwords
    return ssh

def test_connections():
    """Tests connection to each host"""
    if config.RUNNING_IN_DOCKER:
        for host in list(config.TARGET_HOSTS.values()) + list(config.BACKUP_HOSTS.values()):
            logger.info(f"Testing SSH connection to {host.name}")
            try:
                ssh = get_ssh_connection(host)
                transport = ssh.get_transport()
                transport.send_ignore()
            except Exception:
                raise Exception(f"Encountered connection issue with [{host.name}]")
            ssh.close()
            logger.info(f"Successful SSH connection to {host.name}")
    return

if __name__ == '__main__':
    while True:
        if config.config_file_has_been_updated():
            logger.info("Config Updated!!!")
            models.populate_from_config()
            models.validate()
            test_connections()
            _ensure_backup_folders_exist()
            set_jobs()
        else:
            logger.debug("Config File Has Not Updated")
        sleep(10)