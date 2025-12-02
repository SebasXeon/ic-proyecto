pipeline {
    agent any

    environment {
        DOCKER_IMAGE = "ic_app:${BUILD_NUMBER}"
        CODECOV_TOKEN = credentials('codecov-token')
    }

    stages {
        stage('Build App') {
            steps {
                echo "Building FastAPI app..."
                sh 'docker compose build'
            }
        }

        stage('Run Tests & Coverage') {
            steps {
                echo "Running tests inside container with coverage..."
                sh '''
                    docker compose run --rm \
                      -v "$(pwd)":/workspace \
                      -w /workspace \
                      api \
                      pytest --cov=api --cov-report=xml --cov-report=term
                '''
            }
        }

        stage('Upload Coverage to Codecov') {
            steps {
                echo "Uploading coverage report to Codecov..."
                sh '''
                    curl -Os https://uploader.codecov.io/latest/linux/codecov
                    chmod +x codecov
                    ./codecov -f coverage.xml
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    sh "docker build -t ${DOCKER_IMAGE} -f api/Dockerfile ."
                }
            }
        }
    }

    post {
        success {
            echo 'Build completado exitosamente.'
        }
        failure {
            echo 'Error durante el pipeline.'
        }
    }
}
