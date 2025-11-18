pipeline {
    agent any

    environment {
        DOCKER_IMAGE = "ic_app:${BUILD_NUMBER}"
    }

    stages {
        stage('Build App') {
            steps {
                echo "Building FastAPI app..."
                sh 'docker compose build'
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
