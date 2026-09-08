"""
Curated learning resource seed data.

Only real, well-established official documentation sites — never a
guessed or fabricated course/tutorial link, per the spec's explicit
instruction. Admins can add more via the admin panel (courses, books,
practice platforms, etc.) the same way the skill taxonomy is extended in
Phase 2; this seed only covers the "documentation" category, since
that's the one category we can responsibly pre-populate without needing
a live catalog integration.
"""

CURATED_DOCUMENTATION = {
    "Python": ("Python Official Documentation", "https://docs.python.org/3/"),
    "JavaScript": ("MDN JavaScript Guide", "https://developer.mozilla.org/en-US/docs/Web/JavaScript"),
    "TypeScript": ("TypeScript Handbook", "https://www.typescriptlang.org/docs/"),
    "Java": ("Java Documentation", "https://docs.oracle.com/en/java/"),
    "C++": ("C++ Reference", "https://en.cppreference.com/w/"),
    "C#": ("C# Documentation", "https://learn.microsoft.com/en-us/dotnet/csharp/"),
    "Go": ("Go Documentation", "https://go.dev/doc/"),
    "Rust": ("The Rust Book", "https://doc.rust-lang.org/book/"),
    "SQL": ("PostgreSQL Tutorial", "https://www.postgresql.org/docs/current/tutorial.html"),
    "React": ("React Documentation", "https://react.dev/"),
    "Angular": ("Angular Documentation", "https://angular.dev/"),
    "Vue.js": ("Vue.js Guide", "https://vuejs.org/guide/introduction.html"),
    "Django": ("Django Documentation", "https://docs.djangoproject.com/"),
    "Flask": ("Flask Documentation", "https://flask.palletsprojects.com/"),
    "FastAPI": ("FastAPI Documentation", "https://fastapi.tiangolo.com/"),
    "Node.js": ("Node.js Documentation", "https://nodejs.org/en/docs"),
    "Express.js": ("Express.js Documentation", "https://expressjs.com/"),
    "Spring Boot": ("Spring Boot Documentation", "https://docs.spring.io/spring-boot/index.html"),
    "PostgreSQL": ("PostgreSQL Documentation", "https://www.postgresql.org/docs/"),
    "MySQL": ("MySQL Documentation", "https://dev.mysql.com/doc/"),
    "MongoDB": ("MongoDB Documentation", "https://www.mongodb.com/docs/"),
    "Redis": ("Redis Documentation", "https://redis.io/docs/"),
    "AWS": ("AWS Documentation", "https://docs.aws.amazon.com/"),
    "Microsoft Azure": ("Azure Documentation", "https://learn.microsoft.com/en-us/azure/"),
    "Google Cloud Platform": ("Google Cloud Documentation", "https://cloud.google.com/docs"),
    "Docker": ("Docker Documentation", "https://docs.docker.com/"),
    "Kubernetes": ("Kubernetes Documentation", "https://kubernetes.io/docs/home/"),
    "Terraform": ("Terraform Documentation", "https://developer.hashicorp.com/terraform/docs"),
    "Jenkins": ("Jenkins Documentation", "https://www.jenkins.io/doc/"),
    "Git": ("Git Documentation", "https://git-scm.com/doc"),
    "GitHub Actions": ("GitHub Actions Documentation", "https://docs.github.com/en/actions"),
    "Linux": ("The Linux Documentation Project", "https://tldp.org/"),
    "Nginx": ("Nginx Documentation", "https://nginx.org/en/docs/"),
    "TensorFlow": ("TensorFlow Documentation", "https://www.tensorflow.org/learn"),
    "PyTorch": ("PyTorch Documentation", "https://pytorch.org/docs/stable/index.html"),
    "Scikit-learn": ("Scikit-learn Documentation", "https://scikit-learn.org/stable/"),
    "Keras": ("Keras Documentation", "https://keras.io/"),
    "Hugging Face": ("Hugging Face Documentation", "https://huggingface.co/docs"),
    "Pandas": ("Pandas Documentation", "https://pandas.pydata.org/docs/"),
    "NumPy": ("NumPy Documentation", "https://numpy.org/doc/"),
    "Apache Spark": ("Apache Spark Documentation", "https://spark.apache.org/docs/latest/"),
    "Apache Airflow": ("Apache Airflow Documentation", "https://airflow.apache.org/docs/"),
    "Kafka": ("Apache Kafka Documentation", "https://kafka.apache.org/documentation/"),
    "Tableau": ("Tableau Help", "https://help.tableau.com/"),
    "Power BI": ("Power BI Documentation", "https://learn.microsoft.com/en-us/power-bi/"),
    "Pytest": ("Pytest Documentation", "https://docs.pytest.org/"),
    "Jest": ("Jest Documentation", "https://jestjs.io/docs/getting-started"),
    "Selenium": ("Selenium Documentation", "https://www.selenium.dev/documentation/"),
    "Jira": ("Jira Documentation", "https://support.atlassian.com/jira-software-cloud/"),
}


def get_curated_resource(skill_name):
    return CURATED_DOCUMENTATION.get(skill_name)
