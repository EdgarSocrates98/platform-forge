"""GitOps & CI/CD analysis: ArgoCD, Flux, GitHub Actions, GitLab CI,
Dockerfile, Backstage catalog entities."""

from platformforge.cicd.backstage import analyze_backstage
from platformforge.cicd.dockerfile import analyze_dockerfile
from platformforge.cicd.github_actions import analyze_gha
from platformforge.cicd.gitlab_ci import analyze_gitlab_ci
from platformforge.cicd.gitops import analyze_gitops

__all__ = [
           "analyze_backstage",
           "analyze_dockerfile",
           "analyze_gha",
           "analyze_gitlab_ci",
           "analyze_gitops",
]
