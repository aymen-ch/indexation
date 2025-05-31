from django.urls import path
# from . import views
from .aggregation import view as view_aggregation
from .chatbot import view as vchat
from .contextualization import view as context_view
from .path import view as path_view
from .analyse import view as analyse_view

from .Configuration import view as config_view
from .interrogation import view as view_intreogcible
from .detail import view as view_detail
from .contextmenu import view as view_contextmenu
from .dashboard import view as view_dashboard
from .dataBaseManagment import view as view_dataBaseManagment 

urlpatterns = [
    ############################### Analysis ################################### 
    path('fetch_distinct_relations/', analyse_view.fetch_distinct_relations, name='fetch_distinct_relations'),
    path('analyse_fetch_nodes_by_range/', analyse_view.analyse_fetch_nodes_by_range, name='analyse_fetch_nodes_by_range'),
    path('expand_path_from_node/', analyse_view.expand_path_from_node, name='expand_path_from_node'),
    path('get_attribute_values_for_node_type/', analyse_view.get_attribute_values_for_node_type, name='get_attribute_values_for_node_type'),
    path('get_relationship_types_for_node_type/', analyse_view.get_relationship_types_for_node_type, name='get_relationship_types_for_node_type'),
    path('get_relationship_numeric_properties/', analyse_view.get_relationship_numeric_properties, name='get_relationship_numeric_properties'),
    path('calculate_centrality/', analyse_view.calculate_centrality, name='calculate_centrality'),
    path('link_prediction/', analyse_view.link_prediction, name='link_prediction'),
    
    ############################### aggregation ###################################  
    path('agregate/', view_aggregation.aggregate, name='agregate_context'),
    ################################# details #################################
    path('get_incoming_relationship_attributes/', view_detail.get_incoming_relationship_attributes, name='get_incoming_relationship_attributes'),
    path('insert_node_attribute/', view_detail.insert_node_attribute, name='insert_node_attribute'),
    path('get_node_properties/', view_detail.get_node_properties, name='get_node_properties'),
    path('get_relationship_properties/', view_detail.get_relationship_properties, name='get_relationship_properties'),
    path('get_outgoing_relationship_attributes/', view_detail.get_outgoing_relationship_attributes, name='get_outgoing_relationship_attributes'),
    ############################### contextmenu expand + actions ###################################
    path('get_possible_relations/', view_contextmenu.get_possible_relations, name='get_possible_relations'),
    path('extensibility/', view_contextmenu.extensibility, name='extensibility'),
    path('extensibilty_virtuel/', view_contextmenu.extensibilty_virtuel, name='get_virtual_relationships'),
    path('execute_action/', view_contextmenu.execute_action, name='execute_action'),
    path('get_virtual_relation_count/', view_contextmenu.get_virtual_relation_count, name='get_virtual_relation_count'),
    #################################interrogation cible par type de node + rechreche #################################
    path('node-types/', view_intreogcible.get_node_types, name='get_node_types'),
    path('node-types/properties_types/', view_intreogcible.get_node_properties_withType, name='get_node_properties_withType'),
    path('search_cible_type_de_node/', view_intreogcible.search_cible_type_de_node, name='search_nodes'),
    path('recherche/', view_intreogcible.recherche, name='recherche'),
    path('getnodedata/', view_intreogcible.getnodedata, name='getdata'),
    path('getrelationData/', view_intreogcible.getrelationData, name='getrelationData'),
    ################################# contextualization #################################
    path('daira_and_commune/', context_view.get_daira_and_commune, name='get_daira_and_commune'),
    path('filter_affaire_relations/', context_view.filter_affaire_relations, name='filter_affaire_relations'),
    path('all_affaire_types/', context_view.get_all_affaire_types, name='get_all_affaire_types'),
    path('all_wilaya/', context_view.get_all_wilaya, name='all_wilaya'),
    path('dairas/', context_view.get_daira_by_wilaya, name='daira_by_wilaya'),
    path('communes/', context_view.get_commune_by_wilaya_and_daira, name='commune_by_wilaya_and_daira'),
    path('count_affaires/', context_view.count_affaires, name='count_affaires'),
    #################################### chatbot ###############################   
    path('chatbot/', vchat.chatbot, name='chat'),
    path('chatbot/resume/', vchat.chatbot_resume, name='chatbot_resume'),
    path('generate_action/', vchat.chatbot_generate_action, name='action'),
    path('execute_query_graph/', vchat.execute_query_graph, name='execute_query_graph'),
    path('execute_query_table/', vchat.execute_query_table, name='execute_query_table'),
    path('getollamamodeles/', vchat.getollamamodeles, name='getollamamodeles'),
    ############################## path ####################################
    path('get_all_connections/', path_view.get_all_connections, name='get_all_connections'),
    path('shortestpath/', path_view.shortestpath, name='shortestpath'),
    ############################## Data Base Managment  ####################################
    path('list_all_databases/', view_dataBaseManagment.list_all_databases_view, name='list_all_databases_view'),
    path('get_current_database/', view_dataBaseManagment.get_current_database_view, name='get_current_database_view'),
    path('delete_database/', view_dataBaseManagment.delete_database_view, name='delete_database_view'),
    path('create_new_database/', view_dataBaseManagment.create_new_database_view, name='create_new_database_view'),
    path('change_current_database/', view_dataBaseManagment.change_current_database_view, name='change_current_database_view'),
    path('import_file_to_neo4j/', view_dataBaseManagment.import_file_to_neo4j_view, name='import_file_to_neo4j_view'),
    path('database_stats/', view_dataBaseManagment.get_database_stats_view, name='get_database_stats_view'),

    ############################## DashBoard   ####################################
    path('DashBoard_database_stats/', view_dashboard.get_database_stats_view, name='get_database_stats_view'),
    path('DashBoard_get_node_type_counts/', view_dashboard.get_node_type_counts_view, name='get_node_type_counts_view'),
    path('DashBoard_get_affaire_counts_by_wilaya/', view_dashboard.get_affaire_counts_by_wilaya_view, name='get_affaire_counts_by_wilaya_view'),
    path('DashBoard_get_affaire_counts_by_day/', view_dashboard.get_affaire_counts_by_day_view, name='get_affaire_counts_by_day_view'),
    path('DashBoard_get_top_unite_by_affaire_count/', view_dashboard.get_top_unite_by_affaire_count_view, name='get_top_unite_by_affaire_count_view'),
    path('DashBoard_get_relationship_type_counts/', view_dashboard.get_relationship_type_counts_view, name='get_relationship_type_counts'),

    ##############################  config  ####################################
    path('node-config/', config_view.get_node_config, name='node-config'),
    path('update-node-config/', config_view.update_node_config, name='update-node-config'),
    path('add_action/', config_view.add_action, name='add_action'),
    path('get_available_actions/', config_view.get_actions_by_node_type, name='get_available_actions'),
    path('get_predefined_questions/', config_view.get_predefined_questions, name='get_predefined_questions'),
    path('add_predefined_question/', config_view.add_predefined_question, name='add_predefined_question'),
    path('add_aggregation/', config_view.add_aggregation, name='add_aggregation'),
    path('get_aggregations/', config_view.get_aggregations, name='get_aggregations'),
    path('get_schema/', config_view.get_schema, name='get_schema'),
    path('visualizations/save/', config_view.save_visualization, name='save_visualization'),
    path('visualizations/', config_view.get_visualizations, name='get_visualizations'),
]


 

