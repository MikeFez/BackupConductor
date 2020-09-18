import config
import models
from time import sleep
from crontab import CronTab
import os
from loguru import logger
import paramiko

if config.RUNNING_IN_DOCKER:
    cron = CronTab(user=True)

def set_jobs():
    if config.RUNNING_IN_DOCKER:
        logger.info("Removing existing BackupConductor cron tasks")
        cron.remove_all(comment=config.DEFAULT_CRONTAB_COMMENT)
    for backup_host in config.BACKUP_HOSTS.values():
        for directory_data in backup_host.directories:
            set_schedule(backup_host, directory_data)
    return

def set_schedule(backup_host, directory_data):
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

def _ensure_backup_folders_exist():
    folders_per_host = {}
    for backup_host in config.BACKUP_HOSTS.values():
        for directory_data in backup_host.directories:
            target_host = config.TARGET_HOSTS[directory_data.backup_target]
            if target_host not in folders_per_host:
                folders_per_host[target_host] = []
            folders_per_host[target_host].append(f'{target_host.backup_directory}/BackupConductor/{backup_host.name}/{directory_data.name}')
            
    for target_host, directories in folders_per_host.items():
        directory_creation_cmd = 'mkdir -p {' + ','.join(directories) + '}'
        logger.info(f'Creating directories: {directory_creation_cmd}')
        
        if config.RUNNING_IN_DOCKER:
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.connect(target_host.ssh_host, target_host.ssh_port, target_host.ssh_user)  # TODO: Support passwords
            (stdin, stdout, stderr) = ssh.exec_command(directory_creation_cmd)
            ssh.close()
    

def _get_job_cmd(backup_host, directory_data, frequency):
    target_host = config.TARGET_HOSTS[directory_data.backup_target]
    return f'ssh -Te none -p {backup_host.ssh_port} {backup_host.ssh_user}@{backup_host.ssh_host} "tar -C / -cz {directory_data.location}" | ssh -p {target_host.ssh_port} {target_host.ssh_user}@{target_host.ssh_host}  "cat > {target_host.backup_directory}/BackupConductor/{backup_host.name}/{directory_data.name}/$(date \'+%Y-%m-%d_%H-%M-%S\').tar.gz"'
    
if __name__ == '__main__':
    while True:
        if config.config_file_has_been_updated():
            logger.info("Config Updated!!!")
            models.populate_from_config()
            models.validate()
            _ensure_backup_folders_exist()
            set_jobs()
        else:
            logger.debug("Config File Has Not Updated")
        sleep(10)