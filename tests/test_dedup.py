from datetime import timedelta

from conftest import make_article

from news_insights.dedup import DedupConfig, cluster_articles


def test_sample_articles_group_into_expected_stories(sample_articles):
    stories = cluster_articles(sample_articles)
    groups = {tuple(sorted(s.article_ids)) for s in stories}

    assert len(stories) == 15
    assert ("s001", "s002", "s003") in groups  # Barclays buyback, three outlets
    assert ("s004", "s005", "s006") in groups  # September rate decision
    assert ("s007", "s008") in groups  # BP profit warning


def test_same_headline_weeks_apart_stays_separate(sample_articles):
    stories = cluster_articles(sample_articles)
    september = next(s for s in stories if "s004" in s.article_ids)
    october = next(s for s in stories if "s025" in s.article_ids)
    assert september.id != october.id


def test_time_window_is_configurable():
    articles = [
        make_article("a", "Barclays launches share buyback", hours=0),
        make_article("b", "Barclays launches share buyback", hours=100),
    ]
    assert len(cluster_articles(articles, DedupConfig(window=timedelta(hours=72)))) == 2
    assert len(cluster_articles(articles, DedupConfig(window=timedelta(hours=200)))) == 1


def test_story_metadata(sample_articles):
    story = next(s for s in cluster_articles(sample_articles) if "s001" in s.article_ids)
    assert story.sources == ["Sample Wire", "Demo Business Daily", "Example Markets"]
    assert story.first_seen < story.last_seen
    assert story.id.startswith("story-")


def test_story_ids_are_stable(sample_articles):
    first = {s.id for s in cluster_articles(sample_articles)}
    second = {s.id for s in cluster_articles(list(reversed(sample_articles)))}
    assert first == second


def test_empty_input():
    assert cluster_articles([]) == []
