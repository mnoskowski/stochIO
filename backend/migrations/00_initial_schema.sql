CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- USERS
CREATE TABLE IF NOT EXISTS users (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    disabled BOOLEAN DEFAULT FALSE NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- TOPICS
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject VARCHAR(64) NOT NULL CHECK (subject IN ('chemistry', 'math', 'physics')),
    name VARCHAR(128) NOT NULL,
    slug VARCHAR(128) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_topics_subject ON topics(subject);
CREATE INDEX IF NOT EXISTS idx_topics_slug ON topics(slug);

-- QUESTIONS
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    generator_key VARCHAR(64) NOT NULL, -- e.g. 'stoich_molar_mass', 'redox_acidic', 'gas_pv_nrt'
    difficulty SMALLINT NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
    type VARCHAR(32) NOT NULL DEFAULT 'dynamic' CHECK (type IN ('dynamic', 'algorithmic', 'static')),
    flashcardable BOOLEAN DEFAULT TRUE NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL, -- generator parameters, variable ranges, units
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_questions_generator_key ON questions(generator_key);
CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON questions(difficulty);
CREATE INDEX IF NOT EXISTS idx_questions_metadata ON questions USING GIN (metadata);

CREATE TABLE IF NOT EXISTS question_topics (
    question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (question_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_question_topics_topic_id ON question_topics(topic_id);
CREATE INDEX IF NOT EXISTS idx_question_topics_question_id ON question_topics(question_id);

-- FSRS
CREATE TABLE IF NOT EXISTS user_question_progress (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE NOT NULL,
    
    -- FSRS state: stability, difficulty, due, elapsed_days, scheduled_days, reps, lapses, state
    card_data JSONB NOT NULL,
    
    next_review TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    CONSTRAINT uq_user_question_progress UNIQUE (user_id, question_id)
);

-- find all cards due for review for a given user
CREATE INDEX IF NOT EXISTS idx_progress_user_next_review
    ON user_question_progress(user_id, next_review);

-- Partial index for active overdue review queries across all users
CREATE INDEX IF NOT EXISTS idx_progress_due_cards
    ON user_question_progress(next_review);

-- REVIEW LOGS
CREATE TABLE IF NOT EXISTS review_logs (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE NOT NULL,
    
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 4), -- 1: Again, 2: Hard, 3: Good, 4: Easy
    review_time_ms INTEGER DEFAULT 0 NOT NULL, -- time spent solving in milliseconds
    
    -- FSRS audit snapshot: rating, scheduled_days, elapsed_days, review timestamp, state
    log_data JSONB NOT NULL,
    
    -- Dynamic evaluation details (user input, seed, computed correct answer, tolerance)
    evaluation_data JSONB DEFAULT '{}'::jsonb NOT NULL,
    
    reviewed_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_review_logs_user_reviewed ON review_logs(user_id, reviewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_review_logs_question ON review_logs(question_id);

-- Personal topic mastery and stats
CREATE TABLE IF NOT EXISTS user_topic_stats (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE NOT NULL,
    last_activity TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    average_retrievability DOUBLE PRECISION DEFAULT 0.0 NOT NULL CHECK (average_retrievability BETWEEN 0.0 AND 1.0),
    cards_due INTEGER DEFAULT 0 NOT NULL CHECK (cards_due >= 0),
    cards_reviewed INTEGER DEFAULT 0 NOT NULL CHECK (cards_reviewed >= 0),
    
    CONSTRAINT uq_user_topic_stats UNIQUE (user_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_topic_stats_user_id ON user_topic_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_topic_stats_topic_id ON user_topic_stats(topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_stats_user_retrievability ON user_topic_stats(user_id, average_retrievability);
