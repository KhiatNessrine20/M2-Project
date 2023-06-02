from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet 
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link
import networkx as nx   
from itertools import permutations
from operator import attrgetter


class NetworkDiscovery(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]


    def __init__(self, *args, **kwargs):
        super(NetworkDiscovery, self).__init__(*args, **kwargs)
        self.net = nx.DiGraph()
        self.links = {}
        self.switches = {}
        self.switch_ports = {}
        self.topology_api_app= self    
        self.paths= []
        self.monitor_thread = hub.spawn(self._monitor)
    @set_ev_cls(ofp_event.EventOFPStateChange,[MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]
    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(10)

    
    def _request_stats(self, datapath):
        
        self.logger.debug('send stats request: %016x', datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPPortDescStatsRequest(datapath, 0)
        datapath.send_msg(req)

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)


    
    @set_ev_cls(event.EventSwitchEnter)
    def get_topology_data(self, ev):
        #----------------------------------------------- PART I: Getting Switch, links & ports---------------------------------------------------
        #---------------------------------------Getting The switch list & Links + Adding them to the graph ( self.net)----------------------------------
        switch_list = get_switch(self.topology_api_app, None)
        switches = [switch.dp.id for switch in switch_list]
        self.net.add_nodes_from(switches)

        links_list = get_link(self.topology_api_app, None)
        links = [(link.src.dpid, link.dst.dpid, {'port': link.src.port_no}) for link in links_list]
        self.net.add_edges_from(links)
        # ------------------------------------Saving it into the class variable--------------------
        self.links = links
        self.switches = switches

         #------------------------------------- Identifying the  input and output ports for each switch---------------------------------
        for src_dpid, dst_dpid, link_info in links:
            if src_dpid not in self.switch_ports:
                self.switch_ports[src_dpid] = {'in_port': [], 'out_port': []}

            if dst_dpid not in self.switch_ports:
                self.switch_ports[dst_dpid] = {'in_port': [], 'out_port': []}

            #-----------------------------------------We append each of it to the dictionnary--------------------------------------------
            self.switch_ports[src_dpid]['out_port'].append(link_info['port'])
            self.switch_ports[dst_dpid]['in_port'].append(link_info['port'])
            print('---Links are:------')
            print(self.links)
            print('--Switch ports:--------')
            print(self.switch_ports)
            print ("SWITCHES Are:")
            print (self.switches )
            #---------------------------------------------------------------------------------------------------------------------------
         #-------------------------------------------------------Part II: Getting all the possible paths-------------------------------------
         #--------------------------------------------------- Craeting Combi of Switches 2 par 2 ----------------------------------------------
        switch_combinations = permutations(self.switches, 2)
        paths = []  # Init a list ( there is also a class variaable for paths)
        path_id = 1  # ID counter
        for src_dpid, dst_dpid in switch_combinations: # Starting the iteration over the combi
            if src_dpid == 1 and dst_dpid ==4:  #Since it is a directed graph and we will always ping fromm S1 to S4
                path = list(nx.all_shortest_paths(self.net, src_dpid, dst_dpid))  # Networkx Method to get all the shortest paths
                paths.append((path_id, path))  # Store path along with its ID
                path_id += 1  # Increment path ID
       
           # Store each path separately along with its ID
        self.paths = paths
        for path in self.paths: # In order to print the paths as it is stored, we need to itterate over the list
            path_2 = path[1]
            path_3 = path_2[0]
            path_4 = path_2[1]
             # Print the individual paths
            print("--------------Toplogy Paths:----------------------------------")
            print("All Paths are :", path_2)
            print("Path 1 is:", path_3)
            print("Path 2 is:", path_4)
            print("--------------------------------------------------------------")
