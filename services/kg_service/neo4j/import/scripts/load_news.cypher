// ============================================================================
// Load Tourism News from JSON
// This script loads SLTDA news articles and connects them to temporal structure
// ============================================================================

// ============================================================================
// STEP 1: Load News Articles from JSON using APOC
// ============================================================================

CALL apoc.load.json('file: ///data/tourism_news.json') YIELD value

// Extract articles from the news_articles array
UNWIND value.news_articles AS article

// Parse date to extract year, month, day
WITH article,


CASE
 WHEN article.date IS NOT null THEN


CASE
// Try parsing "Month DD, YYYY" format (e.g., "September 19, 2025")
 WHEN article.date =~ '\\w+ \\d+, \\d+' THEN
date(
toString(toInteger(split(article.date, ', ')[1])) + '-' +


CASE split(article.date, ' ')[0]
 WHEN 'January' THEN '01'
 WHEN 'February' THEN '02'
 WHEN 'March' THEN '03'
 WHEN 'April' THEN '04'
 WHEN 'May' THEN '05'
 WHEN 'June' THEN '06'
 WHEN 'July' THEN '07'
 WHEN 'August' THEN '08'
 WHEN 'September' THEN '09'
 WHEN 'October' THEN '10'
 WHEN 'November' THEN '11'
 WHEN 'December' THEN '12'
ELSE '01'
END + '-' +
substring(split(split(article.date, ', ')[0], ' ')[1] + '00', 0, 2)
)
ELSE null
END
ELSE null
END AS parsed_date

// Create unique ID for each article
WITH article, parsed_date,
toLower(replace(substring(article.title, 0, 50), ' ', '_')) + '_' + toString(timestamp()) AS article_id

// Create NewsArticle node
MERGE (n:NewsArticle { id: article_id })
  ON CREATE SET
n.title = article.title,
n.date = parsed_date,
n.image_url = article.image_url,
n.content = article.content,
n.read_more_url = article.read_more_url,
n.scraped_at = article.scraped_at,
n.created_at = datetime(),
n.year =


CASE WHEN parsed_date IS NOT null THEN parsed_date.year ELSE null END,
n.month =


CASE WHEN parsed_date IS NOT null THEN parsed_date.month ELSE null END,
n.day =


CASE WHEN parsed_date IS NOT null THEN parsed_date.day ELSE null END
  ON MATCH SET
n.updated_at = datetime()

// Set category based on content analysis
WITH n
 SET n.category =


CASE
 WHEN toLower(n.title) CONTAINS 'award' OR toLower(n.content) CONTAINS 'award' THEN 'Awards & Recognition'
 WHEN toLower(n.title) CONTAINS 'digital' OR toLower(n.content) CONTAINS 'digital' THEN 'Digital Transformation'
 WHEN toLower(n.title) CONTAINS 'tourism' OR toLower(n.content) CONTAINS 'tourism development' THEN 'Tourism Development'
 WHEN toLower(n.title) CONTAINS 'marine' OR toLower(n.content) CONTAINS 'marine' THEN 'Marine Tourism'
 WHEN toLower(n.title) CONTAINS 'sustainable' OR toLower(n.content) CONTAINS 'sustainable' THEN 'Sustainability'
 WHEN toLower(n.title) CONTAINS 'guide' OR toLower(n.content) CONTAINS 'training' THEN 'Training & Education'
 WHEN toLower(n.title) CONTAINS 'design' OR toLower(n.content) CONTAINS 'guideline' THEN 'Standards & Guidelines'
ELSE 'General News'
END;

// ============================================================================
// STEP 2: Link News to Temporal Structure (Year and Month)
// ============================================================================

// Link to Year nodes
MATCH (n:NewsArticle)
WHERE n.year IS NOT null

WITH n
MERGE (y:Year { year: n.year })
  ON CREATE SET
y.created_at = datetime(),
y.is_leap_year = (n.year % 4 = 0 AND (n.year % 100 <> 0 OR n.year % 400 = 0)),
y.status = 'active'
MERGE (n)-[:PUBLISHED_IN_YEAR]->(y);

// Link to Month nodes
MATCH (n:NewsArticle)
WHERE n.year IS NOT null AND n.month IS NOT null

WITH n
MATCH (y:Year { year: n.year })
MERGE (m:Month { year: n.year, month: n.month })
  ON CREATE SET
m.month_name =


CASE n.month
 WHEN 1 THEN 'January'
 WHEN 2 THEN 'February'
 WHEN 3 THEN 'March'
 WHEN 4 THEN 'April'
 WHEN 5 THEN 'May'
 WHEN 6 THEN 'June'
 WHEN 7 THEN 'July'
 WHEN 8 THEN 'August'
 WHEN 9 THEN 'September'
 WHEN 10 THEN 'October'
 WHEN 11 THEN 'November'
 WHEN 12 THEN 'December'
END,
m.created_at = datetime()
MERGE (n)-[:PUBLISHED_IN_MONTH]->(m)
MERGE (y)-[:HAS_MONTH]->(m);

// ============================================================================
// Link to Country
// ============================================================================

MATCH (n:NewsArticle)
MATCH (c:Country { name: "Sri Lanka" })
MERGE (n)-[:ABOUT_COUNTRY]->(c);

// Link news to Information & Media domain
MATCH (n:NewsArticle)
MATCH (d:Domain)
WHERE d.name IN ["Information & Media", "Tourism Administration"]
MERGE (n)-[:BELONGS_TO_DOMAIN]->(d);

// ============================================================================
// STEP 4: Create News Category nodes and relationships
// ============================================================================

// Get distinct categories
MATCH (n:NewsArticle)
WHERE n.category IS NOT null
WITH DISTINCT n.category AS category_name

MERGE (nc:NewsCategory { name: category_name })
  ON CREATE SET
nc.created_at = datetime(),
nc.description = category_name;

// Link articles to categories
MATCH (n:NewsArticle)
WHERE n.category IS NOT null
MATCH (nc:NewsCategory { name: n.category })
MERGE (n)-[:IN_CATEGORY]->(nc)
MERGE (nc)-[:HAS_ARTICLE]->(n);

// Link news categories to domain
MATCH (nc:NewsCategory)
MATCH (d:Domain { name: "Information & Media" })
MERGE (nc)-[:BELONGS_TO_DOMAIN]->(d);

// Link temporal entities to news (inverse relationships)
MATCH (n:NewsArticle)-[:PUBLISHED_IN_YEAR]->(y:Year)
MERGE (y)-[:HAS_NEWS]->(n);

MATCH (n:NewsArticle)-[:PUBLISHED_IN_MONTH]->(m:Month)
MERGE (m)-[:HAS_NEWS]->(n);

// ============================================================================
// STEP 5: Return summary
// ============================================================================

MATCH (n:NewsArticle)
OPTIONAL MATCH (n)-[:PUBLISHED_IN_YEAR]->(y:Year)
OPTIONAL MATCH (n)-[:PUBLISHED_IN_MONTH]->(m:Month)
OPTIONAL MATCH (n)-[:IN_CATEGORY]->(nc:NewsCategory)
RETURN
count( DISTINCT n) AS total_articles,
count( DISTINCT y) AS articles_with_year,
count( DISTINCT m) AS articles_with_month,
count( DISTINCT nc) AS total_categories,
collect( DISTINCT nc.name) AS categories;
