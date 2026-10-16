import unittest

from bucketer.tags import clean_tags


def tag(name, count=0):
    return {"name": name, "count": count}

class CleanTagsTest(unittest.TestCase):
    def test_lowercases_strips_and_sorts_by_count_then_name(self):
        out = clean_tags([tag(" Stoner Rock ", 100), tag("Hard Rock", 12), tag("desert rock", 12)])
        self.assertEqual([t["name"] for t in out], ["stoner rock", "desert rock", "hard rock"])

    def test_drops_years_decades_and_noise(self):
        out = clean_tags([tag("1991", 47), tag("90s", 30), tag("1990s", 5), tag("seen live", 9),
                          tag("Male Vocalists", 8), tag("grunge", 1)])
        self.assertEqual([t["name"] for t in out], ["grunge"])

    def test_dedupes_keeping_best_count_and_truncates(self):
        out = clean_tags([tag("grunge", 1), tag("Grunge", 50)] + [tag(f"t{i}", 10) for i in range(20)], max_n=3)
        self.assertEqual(out[0], {"name": "grunge", "count": 50})
        self.assertEqual(len(out), 3)

    def test_drops_junk_and_merges_spelling_variants(self):
        out = clean_tags([tag("reissue", 90), tag("wrong track streaming", 80), tag("Synth-pop", 60),
                          tag("synthpop", 40), tag("synth pop", 40), tag("new wave", 20)])
        self.assertEqual([t["name"] for t in out], ["synth-pop", "new wave"])

    def test_vague_tags_rank_below_specific_ones(self):
        out = clean_tags([tag("rock", 100), tag("alternative", 90), tag("post-hardcore", 5)])
        self.assertEqual([t["name"] for t in out], ["post-hardcore", "rock", "alternative"])

    def test_drops_list_membership_and_chatter_tags(self):
        junk = ["1001 albums you must hear before you die", "top metal albums of the decade 2020 - 2029",
                "best of 2013", "allboutguitarcom", "reissue"]
        self.assertEqual(clean_tags([tag(n, 50) for n in junk] + [tag("doom metal", 5)]), [tag("doom metal", 5)])

    def test_keeps_nationality_tags(self):
        out = clean_tags([tag("swedish", 50), tag("death metal", 40)])
        self.assertEqual([t["name"] for t in out], ["swedish", "death metal"])

    def test_drops_echoes_of_excluded_names(self):
        out = clean_tags([tag("Quicksand", 100), tag("manic compression", 50), tag("post-hardcore", 5)],
                         exclude=("Quicksand", "Manic Compression"))
        self.assertEqual([t["name"] for t in out], ["post-hardcore"])

    def test_accepts_none_and_bare_strings(self):
        self.assertEqual(clean_tags(None), [])
        self.assertEqual(clean_tags(["Metal"]), [{"name": "metal", "count": 0}])



if __name__ == "__main__":
    unittest.main()
