W/O COMPOSE FILE
	Build image
		docker build -t hello-python:latest .

		-t hello-python:latest tags the image with a name.
		. means the build context is the current folder.

	Run Image
		docker run --rm hello-python:latest

		--rm removes the container after it exits.
		--name hello-python-latest  

	Start Container
		docker start hello-python


WITH COMPOSE FILE
	build
		docker compose build app

	run	(-d: background)
		docker compose up -d app

	(to update docker env var have to restart vscode)
	build and run	(-d: background)
		docker compose up -d --build app

	down (stops and removes the Compose-created containers and networks)
		docker compose down -v

	tail logs	(show logs from services managed by Compose - last 100 lines)
		docker compose logs -f --tail 100 app

	push to docker.io
		docker compose push app

	build and push
		docker login && docker compose build app && docker compose push app