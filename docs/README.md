# cl-chat-backend
A real-time chatroom backend exercise

## Requirements

### For building and running
- just - https://github.com/casey/just - Used as a command runner 
  - On a Mac with Homebrew, run `brew install just`
- Docker - https://www.docker.com

### For local development
- uv - https://github.com/astral-sh/uv
  - On a Mac with Homebrew, run `brew install uv`

## How to run

### Server
- Run `just` to list all of the recipies
- Run `just run` to run the service in a Docker container
- If you'd like to run the service locally, you can run `just run_local`

Once the service is running, you can view the Swagger doc at https://127.0.0.1:8000/docs

### Client (uv required)
- Run `just client` to start the client
- Once connected the possible commands can be listed by running `/help`

## Known issues and improvements
- consistent logging format
- not currently testing socketio code
- client is purely AI-generated and not tested
- would be beneficial to have code coverage generated
