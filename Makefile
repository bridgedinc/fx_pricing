build:
	pipenv run pip freeze > requirements.txt
	docker build -t bridgedinc/fx-pricing .

push: build
	docker push bridgedinc/fx-pricing

deploy: push
	ansible-playbook -i ansible/hosts_test.yml ansible/site.yml -t bridged
