"""
Initial skill taxonomy seed data.

Structure: list of categories, each with a list of skills, each optionally
with a list of known alias strings. This is loaded by the `flask seed-taxonomy`
CLI command (idempotent — safe to re-run). Admins can extend the taxonomy
further at runtime via /admin/taxonomy without touching this file.
"""

TAXONOMY = [
    {
        "category": "Programming Languages",
        "skills": [
            {"name": "Python", "aliases": ["python programming", "python 3", "py"]},
            {"name": "Java", "aliases": ["java programming"]},
            {"name": "JavaScript", "aliases": ["js", "javascript programming", "ecmascript"]},
            {"name": "TypeScript", "aliases": ["ts"]},
            {"name": "C++", "aliases": ["cpp", "c plus plus"]},
            {"name": "C#", "aliases": ["csharp", "c sharp"]},
            {"name": "Go", "aliases": ["golang"]},
            {"name": "Rust", "aliases": []},
            {"name": "Ruby", "aliases": []},
            {"name": "PHP", "aliases": []},
            {"name": "Swift", "aliases": []},
            {"name": "Kotlin", "aliases": []},
            {"name": "R", "aliases": ["r programming", "r language"]},
            {"name": "SQL", "aliases": ["structured query language"]},
            {"name": "Scala", "aliases": []},
        ],
    },
    {
        "category": "Frameworks",
        "skills": [
            {"name": "React", "aliases": ["reactjs", "react.js"]},
            {"name": "Angular", "aliases": ["angularjs", "angular.js"]},
            {"name": "Vue.js", "aliases": ["vuejs", "vue"]},
            {"name": "Django", "aliases": []},
            {"name": "Flask", "aliases": []},
            {"name": "FastAPI", "aliases": ["fast api"]},
            {"name": "Spring Boot", "aliases": ["spring", "springboot"]},
            {"name": "Express.js", "aliases": ["expressjs", "express"]},
            {"name": "Next.js", "aliases": ["nextjs"]},
            {"name": "Ruby on Rails", "aliases": ["rails"]},
            {"name": ".NET", "aliases": ["dotnet", "asp.net"]},
            {"name": "Node.js", "aliases": ["nodejs", "node"]},
        ],
    },
    {
        "category": "Libraries",
        "skills": [
            {"name": "Pandas", "aliases": []},
            {"name": "NumPy", "aliases": []},
            {"name": "jQuery", "aliases": []},
            {"name": "Redux", "aliases": []},
            {"name": "Matplotlib", "aliases": []},
            {"name": "Seaborn", "aliases": []},
        ],
    },
    {
        "category": "Databases",
        "skills": [
            {"name": "PostgreSQL", "aliases": ["postgres", "postgresql database"]},
            {"name": "MySQL", "aliases": []},
            {"name": "MongoDB", "aliases": ["mongo"]},
            {"name": "Redis", "aliases": []},
            {"name": "SQLite", "aliases": []},
            {"name": "Oracle Database", "aliases": ["oracle db", "oracle"]},
            {"name": "Microsoft SQL Server", "aliases": ["mssql", "sql server"]},
            {"name": "Elasticsearch", "aliases": ["elastic search"]},
            {"name": "DynamoDB", "aliases": []},
            {"name": "Cassandra", "aliases": []},
        ],
    },
    {
        "category": "Cloud",
        "skills": [
            {"name": "AWS", "aliases": ["amazon web services"]},
            {"name": "Microsoft Azure", "aliases": ["azure"]},
            {"name": "Google Cloud Platform", "aliases": ["gcp", "google cloud"]},
            {"name": "Heroku", "aliases": []},
            {"name": "DigitalOcean", "aliases": ["digital ocean"]},
        ],
    },
    {
        "category": "DevOps",
        "skills": [
            {"name": "Docker", "aliases": ["containerization"]},
            {"name": "Kubernetes", "aliases": ["k8s"]},
            {"name": "Jenkins", "aliases": []},
            {"name": "GitHub Actions", "aliases": ["github ci"]},
            {"name": "Terraform", "aliases": []},
            {"name": "Ansible", "aliases": []},
            {"name": "CI/CD", "aliases": ["continuous integration", "continuous deployment"]},
            {"name": "Git", "aliases": ["version control"]},
            {"name": "Linux", "aliases": ["linux administration"]},
            {"name": "Nginx", "aliases": []},
        ],
    },
    {
        "category": "AI/ML",
        "skills": [
            {"name": "TensorFlow", "aliases": []},
            {"name": "PyTorch", "aliases": []},
            {"name": "Scikit-learn", "aliases": ["sklearn", "scikit learn"]},
            {"name": "Keras", "aliases": []},
            {"name": "Natural Language Processing", "aliases": ["nlp"]},
            {"name": "Computer Vision", "aliases": []},
            {"name": "Machine Learning", "aliases": ["ml"]},
            {"name": "Deep Learning", "aliases": []},
            {"name": "Large Language Models", "aliases": ["llm", "llms"]},
            {"name": "Retrieval-Augmented Generation", "aliases": ["rag"]},
            {"name": "Hugging Face", "aliases": ["huggingface"]},
            {"name": "OpenAI API", "aliases": []},
        ],
    },
    {
        "category": "Data Tools",
        "skills": [
            {"name": "Apache Spark", "aliases": ["spark", "pyspark"]},
            {"name": "Apache Airflow", "aliases": ["airflow"]},
            {"name": "Tableau", "aliases": []},
            {"name": "Power BI", "aliases": ["powerbi"]},
            {"name": "Excel", "aliases": ["microsoft excel"]},
            {"name": "dbt", "aliases": ["data build tool"]},
            {"name": "Snowflake", "aliases": []},
            {"name": "Kafka", "aliases": ["apache kafka"]},
        ],
    },
    {
        "category": "Security",
        "skills": [
            {"name": "Penetration Testing", "aliases": ["pentesting", "pen testing"]},
            {"name": "OWASP", "aliases": []},
            {"name": "Network Security", "aliases": []},
            {"name": "Identity and Access Management", "aliases": ["iam"]},
            {"name": "SIEM", "aliases": []},
            {"name": "Cryptography", "aliases": []},
        ],
    },
    {
        "category": "Testing",
        "skills": [
            {"name": "Unit Testing", "aliases": []},
            {"name": "Selenium", "aliases": []},
            {"name": "Pytest", "aliases": ["py.test"]},
            {"name": "Jest", "aliases": []},
            {"name": "Cypress", "aliases": []},
            {"name": "Test-Driven Development", "aliases": ["tdd"]},
        ],
    },
    {
        "category": "Project Management",
        "skills": [
            {"name": "Agile", "aliases": ["agile methodology"]},
            {"name": "Scrum", "aliases": []},
            {"name": "Kanban", "aliases": []},
            {"name": "Jira", "aliases": []},
            {"name": "Product Management", "aliases": []},
            {"name": "Stakeholder Management", "aliases": []},
        ],
    },
    {
        "category": "Soft Skills",
        "skills": [
            {"name": "Communication", "aliases": []},
            {"name": "Leadership", "aliases": []},
            {"name": "Teamwork", "aliases": ["collaboration"]},
            {"name": "Problem Solving", "aliases": []},
            {"name": "Critical Thinking", "aliases": []},
            {"name": "Time Management", "aliases": []},
            {"name": "Adaptability", "aliases": []},
            {"name": "Mentoring", "aliases": []},
        ],
    },
    {
        "category": "Business Skills",
        "skills": [
            {"name": "Data Analysis", "aliases": []},
            {"name": "Business Strategy", "aliases": []},
            {"name": "Financial Modeling", "aliases": []},
            {"name": "Negotiation", "aliases": []},
            {"name": "Market Research", "aliases": []},
        ],
    },
    {
        "category": "Certifications",
        "skills": [
            {"name": "AWS Certified Solutions Architect", "aliases": ["aws csa"]},
            {"name": "PMP", "aliases": ["project management professional"]},
            {"name": "Certified Scrum Master", "aliases": ["csm"]},
            {"name": "CompTIA Security+", "aliases": ["security+"]},
            {"name": "Google Data Analytics Certificate", "aliases": []},
            {"name": "Certified Kubernetes Administrator", "aliases": ["cka"]},
        ],
    },
]
