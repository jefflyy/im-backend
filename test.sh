mkdir -p database/media
python manage.py makemigrations im
python manage.py migrate
coverage run --source DjangoHW,im,utils,websocket -m pytest --junit-xml=xunit-reports/xunit-result.xml
ret=$?
coverage xml -o coverage-reports/coverage.xml
coverage report
exit $ret