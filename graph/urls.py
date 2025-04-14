from django.urls import path
from . import views
from .aggregation import view as view_aggregation
from .chatbot import view as vchat
from .contextualization import view as context_view
from .path import view as path_view
from .analyse import view as analyse_view
from .utility import *
from .sytle import view as style_view
from .interrogation import view as view_intreogcible
from .detail import view as view_detail
from .contextmenu import view as view_contextmenu
urlpatterns = [
    ############################### Analysis ################################### 
    path('Node_clasification/', analyse_view.Node_clasification, name='Node_clasification'),
    path('fetch_distinct_relations/', analyse_view.fetch_distinct_relations, name='fetch_distinct_relations'),
    path('Secteur_Activite/', analyse_view.Secteur_Activite, name='Secteur_Activite'),
    path('calculate_betweenness_centrality/', analyse_view.calculate_betweenness_centrality, name='calculate_betweenness_centrality'),
    ############################### aggregation ###################################  
    path('agregate/', view_aggregation.aggregate, name='agregate_context'),
    path('aggregatehria/', view_aggregation.aggregate_hira, name='aggre_hira'),
    path('aggregate_with_algo/', view_aggregation.aggregate_with_algo, name='aggregate_with_algo'),
    path('ExpandAggregation/', view_aggregation.ExpandAggregation, name='ExpandAggregation'),
    ################################# details #################################
    path('getdata/', view_detail.getdata, name='getdata'),
    path('getrelationData/', view_detail.getrelationData, name='getrelationData'),
    ############################### contextmenu expand + actions ###################################
    path('get_possible_relations/', view_contextmenu.get_possible_relations, name='get_possible_relations'),
    path('get_node_relationships/', view_contextmenu.get_node_relationships, name='get_node_relationships'),
    path('personne_criminal_network/', view_contextmenu.personne_criminal_network, name='personne_criminal_network'),
    #################################interrogation cible par type de node + rechreche #################################
    path('node-types/', view_intreogcible.get_node_types, name='get_node_types'),
    path('node-types/properties/', view_intreogcible.get_node_properties, name='get_node_properties'),
    path('search-nodes/', view_intreogcible.search_nodes, name='search_nodes'),
    path('recherche/', view_intreogcible.recherche, name='recherche'),
    ################################# contextualization #################################
    path('daira_and_commune/', context_view.get_daira_and_commune, name='get_daira_and_commune'),
    path('filter_affaire_relations/', context_view.filter_affaire_relations, name='filter_affaire_relations'),
    path('all_affaire_types/', context_view.get_all_affaire_types, name='get_all_affaire_types'),
    path('all_wilaya/', context_view.get_all_wilaya, name='all_wilaya'),
    path('dairas/', context_view.get_daira_by_wilaya, name='daira_by_wilaya'),
    path('communes/', context_view.get_commune_by_wilaya_and_daira, name='commune_by_wilaya_and_daira'),
    #################################### chatbot ###############################   
    path('chatbot/', vchat.chatbot, name='chat'),
    path('run/', vchat.execute_query, name='execute_query'),
    ############################## path ####################################
    path('get_all_connections/', path_view.get_all_connections4, name='get_all_connections'),
    path('get_all_connections_subgraphe/', path_view.get_all_connections2, name='get_all_connections2'),
    ############################## Data Base Managment  ####################################
    path('list_all_databases/', list_all_databases_view, name='list_all_databases_view'),
    path('get_current_database/', get_current_database_view, name='get_current_database_view'),
    path('create_new_database/', create_new_database_view, name='create_new_database_view'),
    path('change_current_database/', change_current_database_view, name='change_current_database_view'),
    path('import_file_to_neo4j/', import_file_to_neo4j_view, name='import_file_to_neo4j_view'),

    ############################## style config  ####################################
    path('node-config/', style_view.get_node_config, name='node-config'),
    path('update-node-config/', style_view.update_node_config, name='update-node-config'),

]


 

