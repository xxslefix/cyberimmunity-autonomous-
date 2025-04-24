#!/bin/bash
git checkout afcs --
git pull
rm -r /var/www/afcs
cp -r ./ /var/www/afcs
chmod -R 777 /var/www/afcs
systemctl restart apache2