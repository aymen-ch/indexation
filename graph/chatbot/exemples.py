# 1. Properties Questions
exemples = [
    # //////////////////////////////////////  thats all what i can do /////////////////////////////////////////////
   {
        "question": "ما هي الدائرة التي اسمها الفرنسي  Aoulef واسمها العربي أولف؟",
        "query": """
        MATCH (d:Daira) 
        WHERE d.nom_francais = 'Aoulef' 
        AND d.nom_arabe = 'أولف' 
        RETURN d
        """
    },
    {
        "question": "ما هي البلدية التي تقع على خط الطول 1.2345 وخط العرض 30.5678 واسمها الفرنسي Aoulef واسمها العربي أولف؟",
        "query": """
        MATCH (c:Commune) 
        WHERE c.longitude = 1.2345 
        AND c.latitude = 30.5678 
        AND c.nom_francais = 'Aoulef' 
        AND c.nom_arabe = 'أولف' 
        RETURN c
        """
    },
    {
        "question": "ما هي الولاية التي اسمها الفرنسي Adrar واسمها العربي ادرار ؟",
        "query": """
        MATCH (w:Wilaya) 
        WHERE w.nom_francais = 'Adrar' 
        AND w.nom_arabe = 'ادرار' 
        RETURN w
        """
    },
    {
        "question": "ما هي الوحدة التي اسمها الفرنسي Brigade territoriale de la GN Aoulef ونوعها Brigade واسمها العربي الفرقة الإقليمية للدرك الوطني بأولف؟",
        "query": """
        MATCH (u:Unite) 
        WHERE u.nom_francais = 'Brigade territoriale de la GN Aoulef' 
        AND u.Type = 'Brigade' 
        AND u.nom_arabe = 'الفرقة الإقليمية للدرك الوطني بأولف' 
        RETURN u
        """
    },
    {
        "question": "ما هي القضية التي رقمها Drog_1 وتاريخها 17-04-2023 ونوعها مخدرات؟",
        "query": """
        MATCH (a:Affaire) 
        WHERE a.Number = 'Drog_1' 
        AND a.date = '17-04-2023' 
        AND a.Type = 'مخدرات' 
        RETURN a
        """
    },
    {
        "question": "من هو الشخص الذي اسمه  موهوب ولقبه منير وتاريخ ميلاده '22-09-1994' ورقم تعريفه 45339030376158 ورقمه الشخصي 1؟",
        "query": """
        MATCH (p:Personne) 
        WHERE p.firstname = 'موهوب' 
        AND p.lastname = 'منير' 
        AND p.birth_date = '22-09-1994' 
        AND p.national_id = '45339030376158' 
        AND p.num = 1 
        RETURN p
        """
    },
    {
        "question": "ما هو الحساب الافتراضي الذي اسمه Michael Morales ونوعه Facebook ومعرفه '175575809826100؟",
        "query": """
        MATCH (v:Virtuel) 
        WHERE v.Nom = 'Michael Morales' 
        AND v.Type = 'Facebook' 
        AND v.ID = '175575809826100' 
        RETURN v
        """
    },
    {
        "question": "ما هو الهاتف الذي رقمه 0792803473 ومشغله Djezzy؟",
        "query": """
        MATCH (ph:Phone) 
        WHERE ph.num = '0792803473' 
        AND ph.operateur = 'Djezzy' 
        RETURN ph
        """
    },

# 2.//////////////////////////////// Simple Questions//////////////////////////////////////////////////////////
     {
        "question": "ما هي الدوائر التي تنتمي إلى ولاية وهران؟",
        "query": "MATCH path = (d:Daira)-[:appartient]-(w:Wilaya {{nom_arabe: 'وهران'}}) RETURN d"
    },
    {
        "question": "ما هي البلديات التي تنتمي إلى دائرة Ouled Fares ",
        "query": "MATCH (c:Commune)-[:appartient]-(d:Daira {{nom_francais: 'Ouled Fares'}}) RETURN c"
    },
     {
        "question": "ما هي الوحدات التي تنتمي إلى بلدية فنوغيل ",
        "query": "MATCH (u:Unite)-[:situer]-(c:Commune {{nom_arabe: 'فنوغيل'}}) RETURN u"
    },
     {
        "question": "ما هي القضايا التي تعالجها الوحدة  الفرقة الإقليمية ؟",
        "query": "MATCH (u:Unite {{nom_arabe: 'الفرقة الإقليمية'}})-[:Traiter]-(a:Affaire) RETURN a"
    },
    {
        "question": "ما هي أرقام الهواتف التي يمتلكها الشخص الذي يحمل رقم التعريف الوطني 55163071427360؟",
        "query": "MATCH (p:Personne {{nationel_id: '55163071427360'}})-[:Proprietaire]-(ph:Phone) RETURN ph"
    },
    {
        "question": "ما هي جميع المكالمات التي تمت من رقم الهاتف 0771234567؟",
        "query": "MATCH (ph1:Phone {{num: '0771234567'}})-[ph_call:Appel_telephone]-(ph2:Phone) RETURN ph2"
    },
    {
        "question": "ما هي القضايا المرتبطة بالشخص نجلاء قنون؟",
        "query": "MATCH (p:Personne {{firstname: 'نجلاء', lastname: 'قنون'}})-[:Impliquer]-(a:Affaire) RETURN a"
    },
     {
        "question": "ما هي جميع الهواتف التي يمتلكها أشخاص ولدوا بين تاريخ 1980-01-01 و1985-01-01؟",
        "query": """
        MATCH (p:Personne)-[:Proprietaire]-(ph:Phone)
        WHERE p.birth_date >= '1980-01-01' AND p.birth_date <= '1985-12-31'
        RETURN ph
        """
    },
    {
        "question": "من هم الأشخاص الذين لديهم مكالمات تزيد مدتها عن 300 ثانية ومتورطين في قضايا؟",
        "query": """
        MATCH (p:Personne)-[:Proprietaire]-(ph1:Phone)-[rel:Appel_telephone]-(ph2:Phone)
        WHERE rel.duree_sec > 300
        MATCH (p)-[:Impliquer]-(a:Affaire)
        RETURN DISTINCT p
        """
    },
     
#////////////////////////////// 3. Complex Questions//////////////////////////////////////////////////////
    {
        "question": "ما هي جميع القضايا التي تمت معالجتها في بلدية القبة؟",
        "query": "MATCH (a:Affaire)-[:Traiter]-(u:Unite)-[:Situer]-(c:Commune {{nom_arabe: 'القبة'}}) RETURN c"
    },
     {
        "question": "ما هي جميع الأشخاص الذين ولدوا في عام 1990؟",
        "query": "MATCH (p:Personne) WHERE p.birth_date CONTAINS '1990' RETURN p"
    },
     {
        "question": " من هم الأشخاص الذين تورطوا في قضايا بلدية  ذات الاسم الفرنسيFenoughil ",
        "query": """
        MATCH (u:Unite)-[:situer]-(co:Commune {{nom_francais: 'Fenoughil'}})
        MATCH (p:Personne)-[:Impliquer]-(a:Affaire)-[:Traiter]-(u)
        RETURN p.firstname, p.lastname
        """
    },
     {
        "question": " ماهي القضايا التي تتعامل معها ولاية  Alger؟" ,
        "query": """
        MATCH (w:Wilaya {{nom_francais: 'Alger'}})-[:appartient]-(d:Daira)-[:appartient]-(co:Commune)-[:situer]-(u:Unite)-[:Traiter]-(a:Affaire)
        RETURN a
        """
    },
       {
        "question": "ماهي القضايا التي تورط فيها أشخاص على اتصال بالرقم 0654464646؟",
        "query": """
        MATCH (:Phone {{num: '0654464646'}})-[:Appel_telephone]-(:Phone)-[:Proprietaire]-(p:Personne)-[:Impliquer]-(a:Affaire)
        RETURN a
        """
    },
     {
        "question": "من هم الأشخاص المتورطين في قضايا متعددة الأنواع؟",
        "query": """
        MATCH (p:Personne)-[:Impliquer]-(a:Affaire)
        WITH p, COUNT(DISTINCT a.Type) AS type_count
        WHERE type_count > 1
        RETURN p
        """
    },
# 5./////////////////////////////////////////////// Aggregations////////////////////////////////////////////////////
    {
        "question": "ما هو متوسط مدة المكالمات الهاتفية لكل شخص؟",
        "query": "MATCH (p:Personne)-[:Proprietaire]->(ph:Phone)-[ph_call:Appel_telephone]->() RETURN p, AVG(ph_call.duree_sec) AS متوسط_المدة"
    },
    {
        "question": "من هم الأشخاص الذين تورطوا في أكثر من قضية؟",
        "query": "MATCH (p:Personne)-[:Impliquer]->(a:Affaire) WITH p, COUNT(a) AS case_count WHERE case_count > 1 RETURN p"
    },
    {
        "question": "ما هو متوسط عدد القضايا لكل بلدية؟",
        "query": "MATCH (co:Commune)-[:situer]->(u:Unite)-[:Traiter]->(a:Affaire) WITH co, COUNT(a) AS CaseCount RETURN AVG(CaseCount) AS AverageCasesPerCommune"
    },
    {
        "question": "ما هي الولايات الخمس الأكثر تعرضًا للقضايا؟",
        "query": "MATCH (a:Affaire)-[:Traiter]->(u:Unite)-[:situer]->(co:Commune)-[:appartient]->(d:Daira)-[:appartient]->(w:Wilaya) RETURN w.nom_arabe, COUNT(a) AS عدد_القضايا ORDER BY عدد_القضايا DESC LIMIT 5"
    },
    {
        "question": "ما هي البلديات الخمس الأكثر تعرضًا للقضايا؟",
        "query": "MATCH (a:Affaire)-[:Traiter]->(u:Unite)-[:situer]->(co:Commune) RETURN co.nom_arabe, COUNT(a) AS عدد_القضايا ORDER BY عدد_القضايا DESC LIMIT 5"
    },
    {
        "question": "ما هو متوسط مدة المكالمات لكل رقم هاتف يملكه أشخاص متورطين في قضايا؟",
        "query": "MATCH (a:Affaire)-[:Impliquer]->(P:Personne)-[:Proprietaire]->(ph:Phone)-[r:Appel_telephone]->() RETURN ph.num, AVG(r.duree_sec) AS AvgCallDuration"
    },
    {
        "question": "من هم الأشخاص الذين لديهم أكثر من 3 أرقام هواتف؟",
        "query": "MATCH (p:Personne)-[:Proprietaire]->(ph:Phone) WITH p, COUNT(ph) AS phone_count WHERE phone_count > 3 RETURN p"
    },
    {
        "question": "ما هي الوحدات التي تتعامل مع أكثر من 5 قضايا مخدرات؟",
        "query": "MATCH (u:Unite)-[:Traiter]->(a:Affaire {{Type: 'مخدرات'}}) WITH u, COUNT(a) AS drug_cases WHERE drug_cases > 5 RETURN u"
    },
    {
        "question": "ما هو متوسط عدد الأشخاص المتورطين لكل قضية في كل ولاية؟",
        "query": "MATCH (w:Wilaya)-[:appartient]->(d:Daira)-[:appartient]->(c:Commune)-[:situer]->(u:Unite)-[:Traiter]->(a:Affaire)-[:Impliquer]->(p:Personne) WITH w, a, COUNT(p) AS person_count RETURN w.nom_arabe, AVG(person_count) AS AvgPersonsPerCase"
    },
    {
        "question": "ما هي أنواع القضايا التي لها أكثر من 10 أشخاص متورطين؟",
        "query": "MATCH (a:Affaire)-[:Impliquer]->(p:Personne) WITH a.Type AS CaseType, COUNT(p) AS person_count WHERE person_count > 10 RETURN CaseType"
    },

# ////////////////////////////////6. Negative Questions/////////////////////////////////////////////

    {
        "question": "من هم الأشخاص المعنيين بالقضايا الذين لا يملكون أي حسابات افتراضية؟",
        "query": "MATCH (p:Personne)-[:Impliquer]->(a:Affaire) WHERE NOT EXISTS {{ MATCH (p)-[:Proprietaire]->(v:Virtuel) }} RETURN p"
    },
    {
        "question": "من هم الأشخاص الذين ليسوا متورطين في قضية المخدرات ولكن على اتصال بأشخاص متورطين؟",
        "query": "MATCH (p1:Personne)-[:Impliquer]->(a:Affaire {{Type: 'مخدرات'}}) MATCH (p1)-[:Proprietaire]->(ph1:Phone) MATCH (ph1)-[:Appel_telephone]->(ph2:Phone) MATCH (ph2)-[:Proprietaire]->(p2:Personne) WHERE NOT (p2)-[:Impliquer]->(:Affaire {{Type: 'مخدرات'}}) RETURN DISTINCT p2"
    },
    {
        "question": "ماهي الأرقام التي لم تجرِ مكالمات مع الرقم 0666123456؟",
        "query": "MATCH (ph1:Phone) WHERE NOT EXISTS {{ MATCH (ph1)-[:Appel_telephone]->(ph2:Phone {{num: '0666123456'}}) }} RETURN ph1.num AS Numero"
    },
    {
        "question": "ماهي الوحدات التي لا تتعامل مع قضايا التهريب؟",
        "query": "MATCH (u:Unite) OPTIONAL MATCH (u)-[:Traiter]->(a:Affaire {{Type: 'تهريب'}}) WITH u, COUNT(a) AS nb WHERE nb = 0 RETURN u"
    },
    {
        "question": "من هم الأشخاص الذين لم يولدوا في التسعينيات؟",
        "query": "MATCH (p:Personne) WHERE NOT p.birth_date CONTAINS '199' RETURN p"
    },
    {
        "question": "ما هي البلديات التي لا تحتوي على وحدات؟",
        "query": "MATCH (c:Commune) WHERE NOT EXISTS {{ MATCH (c)-[:situer]->(u:Unite) }} RETURN c"
    },
    {
        "question": "من هم الأشخاص الذين لا يمتلكون أرقام هواتف؟",
        "query": "MATCH (p:Personne) WHERE NOT EXISTS {{ MATCH (p)-[:Proprietaire]->(ph:Phone) }} RETURN p"
    },
    {
        "question": "ما هي الوحدات التي لم تعالج أي قضية مخدرات؟",
        "query": "MATCH (u:Unite) WHERE NOT EXISTS {{ MATCH (u)-[:Traiter]->(a:Affaire {{Type: 'مخدرات'}}) }} RETURN u"
    },
    {
        "question": "ما هي الحسابات الافتراضية التي لا يمتلكها أشخاص متورطين في قضايا؟",
        "query": "MATCH (v:Virtuel)-[:Proprietaire]->(p:Personne) WHERE NOT EXISTS {{ MATCH (p)-[:Impliquer]->(a:Affaire) }} RETURN v"
    }
]