// The only Jenkinsfile in this repository. It builds every microservice that
// changed, with the stages implemented in the Shared Library under vars/.
// Library setup in Jenkins is described in README.md.
@Library('instant-lib') _

instantPipeline(
    services        : ['gateway', 'web', 'booking-api', 'identity-api'],
    // ECR repository from the Terraform apply (module.ecr, id instant-app).
    // Confirm with: aws ecr describe-repositories --repository-names instant-app --region us-east-1
    registry        : '908124814208.dkr.ecr.us-east-1.amazonaws.com/instant-app',
    region          : 'us-east-1',
    gitRepoUrl      : 'https://github.com/ossmaahmed/instant.git',
    gitBranch       : 'main',
    gitCredentialsId: 'github',      // Jenkins credential ID (username + token)
    serviceDir      : 'app',         // service folders are app/gateway, app/web, ...
    manifestDir     : 'k8s-eks',
    severity        : 'HIGH,CRITICAL',
    ignoreUnfixed   : false          // any HIGH or CRITICAL fails the scan; set true to ignore ones with no fix yet
)
