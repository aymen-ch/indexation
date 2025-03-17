from django.urls import path
from . import views
from .aggregation import view
from .chatbot import view as vchat
from .contextualization import view as context_view
from .path import view as path_view
from .analyse import view as analyse_view
urlpatterns = [
    
    ############################### Analysis ################################### 
    path('Node_clasification/', analyse_view.Node_clasification, name='Node_clasification'),
    path('fetch_distinct_relations/', analyse_view.fetch_distinct_relations, name='fetch_distinct_relations'),
    ############################### aggregation ###################################  
    path('agregate/', view.aggregate, name='agregate_context'),
    path('aggregatehria/', view.aggregate_hira, name='aggre_hira'),
    path('aggregate_with_algo/', view.aggregate_with_algo, name='aggregate_with_algo'),
    ##################################################################
    path('getdata/', views.getdata, name='getdata'),
    path('get_possible_relations/', views.get_possible_relations, name='get_possible_relations'),
    path('getPersonneCrimes/', views.getPersonneCrimes, name='getPersonneCrimes'),
    path('node-types/', views.get_node_types, name='get_node_types'),
    path('node-types/properties/', views.get_node_properties, name='get_node_properties'),
    path('search-nodes/', views.search_nodes, name='search_nodes'),
    path('get_node_relationships/', views.get_node_relationships, name='get_node_relationships'),
    #################################contextualization#################################
    path('daira_and_commune/', context_view.get_daira_and_commune, name='get_daira_and_commune'),
    path('filter_affaire_relations/', context_view.filter_affaire_relations, name='filter_affaire_relations'),
    path('all_affaire_types/', context_view.get_all_affaire_types, name='get_all_affaire_types'),
    path('all_wilaya/', context_view.get_all_wilaya, name='all_wilaya'),
    path('dairas/', context_view.get_daira_by_wilaya, name='daira_by_wilaya'),
    path('communes/', context_view.get_commune_by_wilaya_and_daira, name='commune_by_wilaya_and_daira'),
    #################################### interogation ###############################   
    path('chatbot/', vchat.chatbot, name='chat'),
    path('run/', vchat.execute_query, name='execute_query'),
    ############################## path ####################################
    path('get_all_connections/', path_view.get_all_connections, name='get_all_connections'),
    path('get_all_connections_subgraphe/', path_view.get_all_connections2, name='get_all_connections2'),
]


 

