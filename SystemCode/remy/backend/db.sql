CREATE DATABASE remy_main;

\c remy_main

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

CREATE TABLE IF NOT EXISTS app_user (
    username      TEXT        PRIMARY KEY,
    password_hash TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT app_user_username_format
        CHECK (username ~ '^[a-z0-9][a-z0-9._-]{2,31}$'),
    CONSTRAINT app_user_password_hash_not_plaintext
        CHECK (length(password_hash) >= 20)
);

DROP TRIGGER IF EXISTS app_user_set_updated_at ON app_user;
CREATE TRIGGER app_user_set_updated_at
    BEFORE UPDATE ON app_user
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS preference (
    username           TEXT        PRIMARY KEY
                                   REFERENCES app_user (username)
                                   ON DELETE CASCADE
                                   ON UPDATE CASCADE,
    special_diet       TEXT,
    cuisine            JSONB,
    preferred_nutrient TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT preference_special_diet_known
        CHECK (special_diet IS NULL
               OR special_diet IN ('halal', 'vegetarian', 'meat'))
);

DROP TRIGGER IF EXISTS preference_set_updated_at ON preference;
CREATE TRIGGER preference_set_updated_at
    BEFORE UPDATE ON preference
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

CREATE INDEX IF NOT EXISTS preference_special_diet_idx
    ON preference (special_diet)
    WHERE special_diet IS NOT NULL;

CREATE INDEX IF NOT EXISTS preference_cuisine_idx
    ON preference (cuisine)
    WHERE cuisine IS NOT NULL;

CREATE TABLE meal(
    id UUID PRIMARY KEY ,
    recipe JSONB
);

CREATE TABLE past_meals(
    id uuid PRIMARY KEY ,
    username TEXT NOT NULL,
    meal_id UUID,
    FOREIGN KEY (meal_id) REFERENCES meal(id)
);

CREATE INDEX IF NOT EXISTS user_meal_lookup_idx ON past_meals(username);

-- Meals a user kept from the ideas on the home page. The whole meal is stored
-- as JSONB so the Saved page can show it without asking the planner again.
-- Mirrored by SAVED_MEAL_DDL in src/app/db.py for databases created before
-- this table existed.
CREATE TABLE IF NOT EXISTS saved_meal (
    username   TEXT        NOT NULL
                           REFERENCES app_user (username)
                           ON DELETE CASCADE
                           ON UPDATE CASCADE,
    recipe_id  TEXT        NOT NULL,
    meal       JSONB       NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (username, recipe_id)
);

-- Whether a user liked a meal, shown newest first on the History page. One row
-- per meal: rating it again changes the like and moves it to the top. The meal
-- is stored whole so History can show it. Mirrored by MEAL_RATING_DDL in
-- src/app/db.py.
CREATE TABLE IF NOT EXISTS meal_rating (
    username  TEXT        NOT NULL
                          REFERENCES app_user (username)
                          ON DELETE CASCADE
                          ON UPDATE CASCADE,
    recipe_id TEXT        NOT NULL,
    liked     BOOLEAN     NOT NULL,
    meal      JSONB       NOT NULL,
    rated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (username, recipe_id)
);

CREATE INDEX IF NOT EXISTS meal_rating_history_idx
    ON meal_rating (username, rated_at DESC);

-- Demo account behind the "Try the demo" button on the sign-in page.
-- Password: remy-demo-account (public on purpose; the account guards nothing).
-- Only runs when the database is first created, like the rest of this file.
INSERT INTO app_user (username, password_hash)
VALUES ('demo', '$argon2id$v=19$m=65536,t=3,p=4$GcIO1+gErvyJyc0IetEyrA$Vzs+eH+7V8nigMYVW824pPCniXgMVuXYbgAB0vmZc54')
ON CONFLICT (username) DO NOTHING;

INSERT INTO preference (username, special_diet, cuisine, preferred_nutrient)
VALUES ('demo', 'meat', '["Chinese", "Malay", "Indian"]'::jsonb, 'Protein')
ON CONFLICT (username) DO NOTHING;

COMMIT;
