IMAGE_NAME := "chatroom_service"

# display list of receipies
@_:
	just --list

# run uv sync, creating uv.lock and .venv
[group('lifecycle')]
install:
	uv sync

# update dependencies
[group('lifecycle')]
update:
	uv sync --upgrade

# clean up the docker, venv, and caches
[group('lifecycle')]
clean: stop
	@echo "Cleaning up Docker resources..."
	@-docker rmi {{IMAGE_NAME}} 2>/dev/null 
	@echo "Removing venv and caches..."
	@rm -rf \
		.venv .pytest_cache \
		.ruff_cache \
		.coverage
	@find . \
		-type d \
		-name "__pycache__" \
		-exec rm -r {} +
	@echo "Done!"

# clean up all resources and re-setup uv
[group('lifecycle')]
fresh: clean install

# build the chatroom_serverimage
[group('run')]
build:
	@echo "Building the image..."
	docker build -t {{IMAGE_NAME}} .

# run the chatroom_server service in a Docker container
[group('run')]
run: build
	@echo "Running the {{IMAGE_NAME}}"
	docker run \
		-d \
		--name {{IMAGE_NAME}} \
		--rm \
		--publish 8000:8000 \
		{{IMAGE_NAME}}

# stops the running chatroom_server service
[group('run')]
stop:
	@echo "Stopping {{IMAGE_NAME}} service..."
	@-docker stop {{IMAGE_NAME}} 2>/dev/null

# runs the server locally (requires uv)
[group('run')]
run_local:
	@APP_ENV=local uv run uvicorn chat.chatroom_server:socket_app --reload

# runs the example client
[group('run')]
client:
	@uv sync --extra client
	@uv run python src/chat/chatroom_client.py

# run the chatroom_server service (non-detached) to view logs
[group('develop')]
run_with_logs: build
	@echo "Running the {{IMAGE_NAME}}"
	docker run \
		--name {{IMAGE_NAME}} \
		--rm \
		--publish 8000:8000 \
		{{IMAGE_NAME}}

# shell into docker container
[group('develop')]
shell: stop build
	@docker run \
		-it \
		--name {{IMAGE_NAME}}_shell \
		--rm \
		--publish 8000:8000 \
		--entrypoint /bin/bash \
		{{IMAGE_NAME}}

# lint the python using ruff
[group('develop')]
lint:
	@uvx ruff check src/

# format python files using ruff
[group('develop')]
format:
	@uvx ruff format src/

# run tests
[group('develop')]
test:
	@uv sync --extra dev
	@uv run -m pytest
