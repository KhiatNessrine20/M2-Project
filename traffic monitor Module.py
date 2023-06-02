from itertools import permutations
from operator import attrgetter
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
from ryu.lib.packet import mpls, ipv4
from collections import defaultdict
import time



class TrafficMonitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]


    def __init__(self, *args, **kwargs):
        super(TrafficMonitor, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor)
        self.flow_speed = {}    # record the flow speed
        self.sleep = 2         # the interval of getting statistic
        self.state_len = 3      
        self.port_stats = {}
        self.port_bandwidth = {}
        self.mac_to_port = {}
        
        


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
    

 
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        msg = ev.msg
        datapath = msg.datapath
        dpid= datapath.id
        flow_data = {}
        self.logger.info('datapath       '
                        'in-port    eth-dst       '
                        'out-port   packets    bytes')
        self.logger.info('---------------- '
                         '-------- ----------------- '
                         '-------- -------- --------')
        for stat in sorted([flow for flow in body if flow.priority == 1],key=lambda flow: (flow.match['in_port'], flow.match['eth_dst'])):
            self.logger.info('%016x %8x  %17s %8x %8d %8d', ev.msg.datapath.id, stat.match['in_port'], stat.match['eth_dst'], stat.instructions[0].actions[0].port, stat.packet_count, stat.byte_count)
            #-----------------------------------------Storing the stats into variables------------------------------------------------------
            in_port = stat.match['in_port']
            eth_dst = stat.match['eth_dst']
            out_port = stat.instructions[0].actions[0].port
        # --------------------------------------------Getting the byte count and current time-----------------------------------------------
            byte_count = stat.byte_count
            current_time = time.time()
        
        # -----------------------------------------------Creating a key for each flow----------------------------------------------------
            flow_key = (dpid, in_port, eth_dst, out_port)
        
        # ---------------------------------------------Checking if the flow key exists in the dictionary ---------------------------------
            if flow_key in flow_data:
                prev_byte_count, prev_time = flow_data[flow_key]
            
            #-------------------------------------------------- PART I: Calculating Flow Speed ------------------------------------------------------
                time_diff = current_time - prev_time # Time diffrence ( T1 & T2)
                byte_diff = byte_count - prev_byte_count  #Byte Diffrence
            # -----------------------------------------------Speed calculation starts-----------------------------------------------------------
                flow_speed = byte_diff / time_diff  # Speed 1: Byte diff /Time Diff
                speed = byte_diff* 8 /time_diff  # Speed 2: Coberting frome Byte to bit ( *8) ==> bits/s
                speed_Mbs = speed /1000           #Converting it to Mb/s
                #--------------------------------------------------------------------------------------------------------------------------------
                #----------------------------------------Part II: Bandwidth Calculation: --------------------------------------------------------
                capacity = 1000000                #Maximum Link capacity supposed  --1G-
                capacity_m = capacity /1000       # Converting it to Mega
                if speed_Mbs < 0:                 # As the byte count may decrese , the speed will be negative and in order to not impact the bw Calculations 
                    speed_max = max(speed_Mbs, 0)  # To avoid negative values , max function will return the biggest value ( which is 0)
                    diff= capacity_m - speed_max   # As the free bw is substracted from the link capacity 
                    av_bw = max (diff,0)          # av_bw = free bandwidth 
                else:                           # if the speed is not negative then we substract directly 
                    diff= capacity_m - speed_Mbs
                    av_bw = max (diff,0)

                 # ---------------------------------Printing Speed values--------------------------------------------------------------------------
                print(f"Flow Speed for {flow_key}: {flow_speed} Bytes/s")  # We print the speed in Bytes
                print("Flow Speed for {flow_key}:", speed_Mbs," Mb/s")  # speed in Mb/s
                print("Available free Bandwidth:", av_bw ,"M")   # Printing the available bandwidth in Mega too 
                #------------------------Updating the flow data in the dictionary-------------------------------------------------------------
            flow_data[flow_key] = (byte_count, current_time)
        #---------------------------------------------------------------------------------------------------------------------------------------
    

    

   
        