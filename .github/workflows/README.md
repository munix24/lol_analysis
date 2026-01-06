# GitHub Actions Workflows

## Docker Build and Push Workflow

This repository is configured to automatically build and push Docker images to Docker Hub whenever code is committed.

### Workflow Triggers

The Docker workflow (`docker-publish.yml`) is triggered on:

1. **Push to main/master branch**: Builds and pushes the image with the `latest` tag
2. **Pull Requests**: Builds the image (without pushing) to verify the Docker build works
3. **Tags** (e.g., `v1.0.0`): Builds and pushes with version tags

### Required GitHub Secrets

To enable automatic Docker image pushing, you need to configure the following secrets in your GitHub repository:

#### Setting up secrets:

1. Go to your GitHub repository
2. Click on **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add the following secrets:

| Secret Name | Description | Example Value |
|------------|-------------|---------------|
| `DOCKER_USERNAME` | Your Docker Hub username | `munix244` |
| `DOCKER_TOKEN` | Your Docker Hub password or access token | `dckr_pat_...` (recommended: use access token) |

#### How to get a Docker Hub Access Token (Recommended):

1. Log in to [Docker Hub](https://hub.docker.com/)
2. Go to **Account Settings** → **Security** → **Access Tokens**
3. Click **New Access Token**
4. Give it a description (e.g., "GitHub Actions")
5. Set permissions to **Read, Write, Delete**
6. Copy the token and use it as `DOCKER_TOKEN`

### Docker Image Details

- **Registry**: Docker Hub (`docker.io`)
- **Image Name**: `munix244/lol_analysis_app`
- **Tags Generated**:
  - `latest`: For pushes to the main/master branch
  - `<version>`: For semantic version tags (e.g., `1.2.3` from tag `v1.2.3`)
  - `<branch>-<sha>`: For feature branches with commit SHA

### Workflow Features

- ✅ Builds Docker image on every push and pull request
- ✅ Only pushes images on actual commits (not PRs)
- ✅ Uses Docker layer caching for faster builds
- ✅ Supports multi-platform builds (linux/amd64)
- ✅ Automatically tags with version numbers from git tags
- ✅ Adds proper metadata and labels to images

### Usage Examples

#### Trigger a build on main branch:
```bash
git add .
git commit -m "Update application code"
git push origin main
```

#### Create a versioned release:
```bash
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

This will create images with tags: `1.0.0`, `1.0`, `1`, and `latest`

### Troubleshooting

If the workflow fails:

1. **Check secrets**: Ensure `DOCKER_USERNAME` and `DOCKER_TOKEN` are set correctly
2. **Check Docker Hub login**: Verify your Docker Hub credentials are valid
3. **Check Dockerfile**: Ensure the Dockerfile builds locally: `docker build -t test .`
4. **View workflow logs**: Go to the **Actions** tab in GitHub to see detailed logs

### Local Testing

Before pushing, you can test the Docker build locally:

```bash
# Build the image
docker build -t munix244/lol_analysis_app:test .

# Run the container (requires MongoDB to be running - see main README.txt)
docker run --rm -e riotapikey="your-key" -e dbserverandport="mongodb://localhost:27017" munix244/lol_analysis_app:test
```

**Note**: This application requires MongoDB as a database backend. See the main README.txt for MongoDB setup instructions.
