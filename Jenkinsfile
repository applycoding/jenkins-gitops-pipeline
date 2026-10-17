// Declarative pipeline for the status-api sample.
// Portfolio demo: registry push and GitOps push are skipped when the
// corresponding variables are empty. This file does not deploy to a cluster.

pipeline {
    agent any

    options {
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    environment {
        IMAGE = 'ghcr.io/placeholder/status-api'
        REGISTRY = 'ghcr.io'
    }

    stages {
        stage('Prepare') {
            steps {
                checkout scm
                sh 'python3 -m venv .venv'
                sh '.venv/bin/pip install -r service/requirements.txt -r requirements-dev.txt'
            }
        }

        stage('Lint') {
            steps {
                sh '.venv/bin/ruff check service scripts tests'
            }
        }

        stage('Test') {
            steps {
                sh '.venv/bin/pytest'
            }
        }

        stage('Build image') {
            steps {
                sh 'docker build -t "$IMAGE:sha-$GIT_COMMIT" service'
            }
        }

        stage('Trivy scan') {
            steps {
                sh 'trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed "$IMAGE:sha-$GIT_COMMIT"'
            }
        }

        stage('Push') {
            when {
                branch 'main'
            }
            steps {
                sh '''
                    set -eu
                    if [ -z "${REGISTRY_USER:-}" ] || [ -z "${REGISTRY_PASSWORD:-}" ]; then
                      echo "PLACEHOLDER: REGISTRY_USER and REGISTRY_PASSWORD are not set. Image was not pushed."
                      exit 0
                    fi
                    printf %s "${REGISTRY_PASSWORD}" | docker login "${REGISTRY}" -u "${REGISTRY_USER}" --password-stdin
                    docker push "${IMAGE}:sha-${GIT_COMMIT}"
                '''
            }
        }

        stage('Bump GitOps tag') {
            when {
                branch 'main'
            }
            steps {
                sh '''
                    set -eu
                    python3 scripts/promote.py set --overlay dev --tag "sha-${GIT_COMMIT}"
                    git add deploy/overlays/dev/kustomization.yaml
                    if git diff --cached --quiet; then
                      echo "Dev overlay already matches sha-${GIT_COMMIT}."
                    else
                      git -c user.name="Arpan Bom" -c user.email="applycoding@gmail.com" commit -m "chore(gitops): set dev image to sha-${GIT_COMMIT}"
                    fi
                    if [ -z "${GITOPS_PUSH_URL:-}" ]; then
                      echo "PLACEHOLDER: GITOPS_PUSH_URL is not set. Dev manifest commit was not pushed."
                    else
                      git push "${GITOPS_PUSH_URL}" HEAD:main
                    fi
                '''
            }
        }

        stage('Promote to staging') {
            when {
                branch 'main'
            }
            steps {
                sh '''
                    set -eu
                    python3 scripts/promote.py promote --source dev --target staging
                    git add deploy/overlays/staging/kustomization.yaml
                    if git diff --cached --quiet; then
                      echo "Staging overlay already matches dev."
                    else
                      git -c user.name="Arpan Bom" -c user.email="applycoding@gmail.com" commit -m "chore(gitops): promote image tag from dev to staging"
                    fi
                    if [ -z "${GITOPS_PUSH_URL:-}" ]; then
                      echo "PLACEHOLDER: GITOPS_PUSH_URL is not set. Staging manifest commit was not pushed."
                    else
                      git push "${GITOPS_PUSH_URL}" HEAD:main
                    fi
                '''
            }
        }

        stage('Promote to prod') {
            when {
                branch 'main'
            }
            options {
                timeout(time: 1, unit: 'HOURS')
            }
            input {
                message 'Promote the staging image tag to production?'
                ok 'Promote'
            }
            steps {
                sh '''
                    set -eu
                    python3 scripts/promote.py promote --source staging --target prod
                    git add deploy/overlays/prod/kustomization.yaml
                    if git diff --cached --quiet; then
                      echo "Prod overlay already matches staging."
                    else
                      git -c user.name="Arpan Bom" -c user.email="applycoding@gmail.com" commit -m "chore(gitops): promote image tag from staging to prod"
                    fi
                    if [ -z "${GITOPS_PUSH_URL:-}" ]; then
                      echo "PLACEHOLDER: GITOPS_PUSH_URL is not set. Prod manifest commit was not pushed."
                    else
                      git push "${GITOPS_PUSH_URL}" HEAD:main
                    fi
                '''
            }
        }
    }

    post {
        always {
            echo 'Pipeline finished. This demo does not deploy to a cluster.'
        }
    }
}
