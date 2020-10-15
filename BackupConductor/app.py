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


def remove_jobs():
    logger.info("Removing existing BackupConductor cron tasks")
    cron.remove_all(comment=config.DEFAULT_CRONTAB_COMMENT)

    
def set_jobs():
    if config.RUNNING_IN_DOCKER:
        remove_jobs()
    for backup_host in config.BACKUP_HOSTS.values():
        for directory_data in backup_host.directories:
            set_schedule(backup_host, directory_data)


def set_schedule(backup_host, directory_data):
    """Generate the crontab schedule"""
    logger.info(f"Configuring backups for {backup_host.name}::{directory_data.name}")
    if config.RUNNING_IN_DOCKER:
        if directory_data.frequency.hourly.enabled:
            job = cron.new(command=_get_job_cmd(backup_host, directory_data, 'hourly', directory_data.frequency.hourly.retain), comment=config.DEFAULT_CRONTAB_COMMENT)
            job.hour.every(1)
            cron.write()
        if directory_data.frequency.daily.enabled:
            job = cron.new(command=_get_job_cmd(backup_host, directory_data, 'daily', directory_data.frequency.daily.retain), comment=config.DEFAULT_CRONTAB_COMMENT)
            job.every().dom()
            cron.write()
        if directory_data.frequency.weekly.enabled:
            job = cron.new(command=_get_job_cmd(backup_host, directory_data, 'weekly', directory_data.frequency.weekly.retain), comment=config.DEFAULT_CRONTAB_COMMENT)
            job.dow.on('SUN')
            job.minute.on(0)
            job.hour.on(0)
            cron.write()
        if directory_data.frequency.monthly.enabled:
            job = cron.new(command=_get_job_cmd(backup_host, directory_data, 'monthly', directory_data.frequency.monthly.retain), comment=config.DEFAULT_CRONTAB_COMMENT)
            job.every().month()
            job.minute.on(0)
            job.hour.on(0)
            job.day.on(1)
            cron.write()
    return

def get_frequency_data(directory_data):
    return {freq_name.lower(): freq_data.retain for freq_name, freq_data in vars(directory_data.frequency).items() if freq_data.enabled is True}

def _ensure_backup_folders_exist():
    """Generate backup folders on target"""
    folders_per_host = {}
    for backup_host in config.BACKUP_HOSTS.values():
        for directory_data in backup_host.directories:
            frequencies = get_frequency_data(directory_data).keys()
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
            
            
def _prune_old_backups():
    """Pune backups outside of the keep amount"""
    retain_per_dir = {}
    for backup_host in config.BACKUP_HOSTS.values():
        for directory_data in backup_host.directories:
            frequencies = get_frequency_data(directory_data)
            target_host = config.TARGET_HOSTS[directory_data.backup_target]
            if target_host not in retain_per_dir:
                folders_per_host[target_host] = {}
            for frequency, retain_amount in frequencies:
                retain_per_dir[target_host][f'{target_host.backup_directory}/BackupConductor/{backup_host.name}/{directory_data.name}/{frequency}'] = retain_amount

    for target_host, directory_data in retain_per_dir.items():
        prune_cmd = []
        for directory, retain_amount in directory_data.items():
            prune_cmd.append(f"cd {directory} && rm `ls -t | awk 'NR>{retain_amount}'`")
        logger.info(f'Pruning directories on {target_host.name}')
        logger.info("; ".join(prune_cmd))
        if config.RUNNING_IN_DOCKER:
            ssh = get_ssh_connection(target_host)
            (stdin, stdout, stderr) = ssh.exec_command("; ".join(prune_cmd))
            ssh.close()
    

def _get_job_cmd(backup_host, directory_data, frequency, retain):
    target_host = config.TARGET_HOSTS[directory_data.backup_target]
    target_dir = f'{target_host.backup_directory}/BackupConductor/{backup_host.name}/{directory_data.name}/{frequency}'
    retain_cmd = f" && rm `ls -t | awk 'NR>{retain}'`" if retain is not None else ""
    return f'ssh -Te none -p {backup_host.ssh_port} {backup_host.ssh_user}@{backup_host.ssh_host} "tar -C / -cz {directory_data.location}" | ssh -p {target_host.ssh_port} {target_host.ssh_user}@{target_host.ssh_host}  "cd {target_dir} && cat > $(date \'+%Y-%m-%d_%H-%M-%S\').tar.gz{retain_cmd}"'

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
    display_if_not_enabled = True
    while True:
        if config.config_file_has_been_updated():
            logger.info("Config Updated!!!")
            models.populate_from_config()
            models.validate()
            
                
            if not config.ENABLED and display_if_not_enabled:
                logger.warning("Backup Conductor Is Disabled!")
                if config.RUNNING_IN_DOCKER:
                    remove_jobs()
                display_if_not_enabled = False
            elif config.ENABLED and not display_if_not_enabled:
                logger.info("Backup Conductor Has Been Enabled!")
                display_if_not_enabled = True
                
            if config.ENABLED:
                test_connections()
                _ensure_backup_folders_exist()
                set_jobs()
        else:
            logger.debug("Config File Has Not Updated")
        sleep(10)