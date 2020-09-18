build:
	docker build \
		--tag backup_conductor:latest \
		.

run:
	docker run \
		--rm \
		-it \
		-v $(CURDIR)/config:/config \
		-v ~/.ssh:/ssh:ro \
		--name BackupConductor \
		backup_conductor:latest

enter:
	docker run \
		--rm \
		-it \
		-e ENTER=true \
		-v $(CURDIR)/config:/config \
		-v ~/.ssh:/ssh:ro \
		--name BackupConductor \
		backup_conductor:latest

run_test:
	docker run \
		--rm \
		-it \
		-v $(CURDIR)/config:/config
		-v ~/.ssh:/ssh:ro \
		-v $(CURDIR)/BackupConductor:/opt/BackupConductor \
		--name BackupConductor \
		backup_conductor:latest