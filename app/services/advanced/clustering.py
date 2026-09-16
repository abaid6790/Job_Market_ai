"""
Semantic job clustering.

Groups analyzed job postings into clusters using TF-IDF + KMeans — the
same classical vector-space approach Phase 6 uses for similarity, kept
deliberately consistent rather than introducing a second, heavier
embedding stack for one optional feature.

Cluster labels are NOT invented: each cluster is labelled with its own
highest-weighted TF-IDF terms and the skills that actually appear most
often in that cluster's jobs. If there isn't enough data to form
meaningful clusters, that's reported rather than forcing jobs into
arbitrary groups.
"""
from collections import Counter

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from app.models import Job

MIN_JOBS_FOR_CLUSTERING = 6
MAX_CLUSTERS = 6
TERMS_PER_CLUSTER = 6


def _choose_cluster_count(job_count):
    # Roughly sqrt-based, clamped — enough clusters to be informative
    # without slicing a small dataset into near-singleton groups.
    return max(2, min(MAX_CLUSTERS, job_count // 3))


def cluster_jobs():
    jobs = (
        Job.query.filter_by(status="completed")
        .filter(Job.raw_text.isnot(None))
        .order_by(Job.created_at.desc())
        .limit(500)
        .all()
    )
    jobs = [j for j in jobs if (j.raw_text or "").strip()]

    if len(jobs) < MIN_JOBS_FOR_CLUSTERING:
        return {
            "available": False,
            "reason": (
                f"Insufficient data — clustering needs at least "
                f"{MIN_JOBS_FOR_CLUSTERING} analyzed jobs with text "
                f"(currently {len(jobs)})."
            ),
        }

    texts = [j.raw_text for j in jobs]

    try:
        vectorizer = TfidfVectorizer(stop_words="english", max_features=2000, min_df=1)
        matrix = vectorizer.fit_transform(texts)
    except ValueError:
        return {
            "available": False,
            "reason": "Job text didn't contain enough distinct vocabulary to cluster.",
        }

    if matrix.shape[1] == 0:
        return {
            "available": False,
            "reason": "Job text didn't contain enough distinct vocabulary to cluster.",
        }

    n_clusters = _choose_cluster_count(len(jobs))
    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = model.fit_predict(matrix)

    feature_names = vectorizer.get_feature_names_out()
    centroids = model.cluster_centers_

    clusters = []
    for cluster_index in range(n_clusters):
        member_jobs = [jobs[i] for i, label in enumerate(labels) if label == cluster_index]
        if not member_jobs:
            continue

        # Top TF-IDF terms for this centroid — a real, data-derived label.
        top_term_indices = centroids[cluster_index].argsort()[::-1][:TERMS_PER_CLUSTER]
        top_terms = [str(feature_names[i]) for i in top_term_indices]

        skill_counter = Counter()
        for job in member_jobs:
            for js in job.job_skills.all():
                skill_counter[js.skill.name] += 1

        clusters.append(
            {
                "index": cluster_index,
                "size": len(member_jobs),
                "top_terms": top_terms,
                "top_skills": [name for name, _ in skill_counter.most_common(6)],
                "sample_titles": [j.title or "Untitled" for j in member_jobs[:5]],
            }
        )

    clusters.sort(key=lambda c: c["size"], reverse=True)

    return {
        "available": True,
        "total_jobs": len(jobs),
        "cluster_count": len(clusters),
        "clusters": clusters,
        "method_note": (
            "Clusters are derived from TF-IDF term similarity across job descriptions. "
            "Labels are the most distinctive terms and most common skills in each cluster — "
            "they are descriptive of the data, not predefined categories."
        ),
    }
