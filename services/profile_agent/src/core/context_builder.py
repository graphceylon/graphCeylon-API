class ProfileContextBuilder:

    def build_context(self, db_prefs: dict, query_prefs: dict):
        merged = {**db_prefs, **query_prefs}
        source = {}

        for k in merged:
            source[k] = "query" if k in query_prefs else "db"

        return {
            "effective_preferences": merged,
            "preference_sources": source
        }
