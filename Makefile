build:
	pipenv run pip freeze > requirements.txt
	docker build -t registry.antonskvortsov.com/bridged .

push: build
	docker push registry.antonskvortsov.com/bridged

deploy: push
	ansible-playbook -i ansible/hosts_test.yml ansible/site.yml -t bridged
