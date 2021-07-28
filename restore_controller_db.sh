#!/bin/bash
date
cd ~pi/controller/controller
>> restore.log 2>> restore.err
if [ -e /mnt/controller/backup/controller.db.backup ]
then
	rm controller.db
	cp /mnt/controller/backup/controller.db.backup controller.db
	sqlite3 controller.db "pragma journal_mode=WAL;"
fi
echo "Restore completed"
