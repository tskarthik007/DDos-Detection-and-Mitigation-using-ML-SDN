import csv
from ryu.controller import ofp_event  
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import in_proto
from ryu.lib.packet import arp
from ryu.lib.packet import ipv4
from ryu.lib.packet import icmp
from ryu.lib.packet import tcp
from ryu.lib.packet import udp
from sklearn.impute import SimpleImputer 

import switch 
from datetime import datetime 

import pandas as pd 
from ryu.ofproto import ofproto_v1_3_parser as ofparser
import joblib

class SimpleMonitor13(switch.SimpleSwitch13):

    def __init__(self, *args, **kwargs):
        super(SimpleMonitor13, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self.monitor)
        self.model=joblib.load('RF_model.joblib')
        
    # This function is used to register and deresigter datapath(switchs) from the controller
    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
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

    # func passed to ryu thread to asycn probe the datapath for stats      
    def monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)  
            hub.sleep(10)
            # print("calling the predict fn")
            # self.flow_predict()
    
    # func requesting flow stats from datapath
    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    # func handling flow stats reply from the datapath
    # this func is called every 10 seconds
    # it parse the flow stats reply and passes the data to the predict function
    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        timestamp = datetime.now()
        timestamp = timestamp.timestamp()

        # with open("PredictFlowStatsfile.csv", mode="w", newline='') as file0:
        #     writer = csv.writer(file0)
        #     writer.writerow(['timestamp', 'datapath_id', 'flow_id', 'ip_src', 'tp_src', 'ip_dst', 'tp_dst', 'ip_proto', 'icmp_code', 'icmp_type',
        #                      'flow_duration_sec', 'flow_duration_nsec', 'idle_timeout', 'hard_timeout', 'flags', 'packet_count', 'byte_count',
        #                      'packet_count_per_second', 'packet_count_per_nsecond', 'byte_count_per_second', 'byte_count_per_nsecond'])

        body = ev.msg.body
        icmp_code = -1
        icmp_type = -1
        tp_src = 0
        tp_dst = 0

        flow_data=[]

        for stat in sorted([flow for flow in body if (flow.priority == 1)], key=lambda flow:
                            (flow.match['eth_type'], flow.match['ipv4_src'], flow.match['ipv4_dst'], flow.match['ip_proto'])):

            ip_src = stat.match['ipv4_src']
            ip_dst = stat.match['ipv4_dst']
            ip_proto = stat.match['ip_proto']

            if stat.match['ip_proto'] == 1:
                icmp_code = stat.match['icmpv4_code']
                icmp_type = stat.match['icmpv4_type']

            elif stat.match['ip_proto'] == 6:
                tp_src = stat.match['tcp_src']
                tp_dst = stat.match['tcp_dst']

            elif stat.match['ip_proto'] == 17:
                tp_src = stat.match['udp_src']
                tp_dst = stat.match['udp_dst']

            flow_id = f'{ip_src}{tp_src}{ip_dst}{tp_dst}{ip_proto}'

            try:
                packet_count_per_second = stat.packet_count / stat.duration_sec
                packet_count_per_nsecond = stat.packer_count / stat.duration_nsec

            except:
                packet_count_per_second = 0
                packet_count_per_nsecond = 0

            try:
                byte_count_per_second = stat.byte_count / stat.duration_sec
                byte_count_per_nsecond = stat.byte_count / stat.duration_nsec
            except:
                byte_count_per_second = 0
                byte_count_per_nsecond = 0

            

            flow_data.append([timestamp, ev.msg.datapath.id, flow_id, ip_src, tp_src, ip_dst, tp_dst, stat.match['ip_proto'], icmp_code, icmp_type,
                            stat.duration_sec, stat.duration_nsec, stat.idle_timeout, stat.hard_timeout, stat.flags, stat.packet_count,
                            stat.byte_count, packet_count_per_second, packet_count_per_nsecond, byte_count_per_second,
                            byte_count_per_nsecond])
            
            # flow_data.writerow([timestamp, ev.msg.datapath.id, flow_id, ip_src, tp_src, ip_dst, tp_dst, stat.match['ip_proto'], icmp_code, icmp_type,
            #                  stat.duration_sec, stat.duration_nsec, stat.idle_timeout, stat.hard_timeout, stat.flags, stat.packet_count,
            #                  stat.byte_count, packet_count_per_second, packet_count_per_nsecond, byte_count_per_second,
            #                  byte_count_per_nsecond])
            
            # print(f'reply of datapath {ev.msg.datapath.id} received and flow_data is {flow_data}') 
            self.flow_predict(flow_data)

    # func to predict the flow and decide the action
    def flow_predict(self,flow_data):
        try:
            # predict_flow_dataset = pd.read_csv('PredictFlowStatsfile.csv')
            predict_flow_dataset = pd.DataFrame(flow_data, columns=['timestamp', 'datapath_id', 'flow_id', 'ip_src', 'tp_src', 'ip_dst', 'tp_dst',
                                                                 'ip_proto', 'icmp_code', 'icmp_type', 'flow_duration_sec', 'flow_duration_nsec',
                                                                 'idle_timeout', 'hard_timeout', 'flags', 'packet_count', 'byte_count',
                                                                 'packet_count_per_second', 'packet_count_per_nsecond', 'byte_count_per_second',
                                                                 'byte_count_per_nsecond'])

            if predict_flow_dataset.empty:
                print("CSV file is empty. Skipping flow prediction.")
                return

            if predict_flow_dataset.isnull().values.any():
                print("Skipping flow prediction due to NaN values in the dataset.")
                return

            df_block=predict_flow_dataset.copy()


            predict_flow_dataset.iloc[:, 2] = predict_flow_dataset.iloc[:, 2].str.replace('.', '')
            predict_flow_dataset.iloc[:, 3] = predict_flow_dataset.iloc[:, 3].str.replace('.', '')
            predict_flow_dataset.iloc[:, 5] = predict_flow_dataset.iloc[:, 5].str.replace('.', '')

            X_predict_flow = predict_flow_dataset.iloc[:, :].values
            X_predict_flow = X_predict_flow.astype('float64')

            y_flow_pred = self.model.predict(X_predict_flow)

            legitimate_trafic = 0
            ddos_trafic = 0

            for i in y_flow_pred:
                if i == 0:
                    legitimate_trafic += 1
                else:
                    ddos_trafic += 1
                    victim = int(predict_flow_dataset.iloc[i, 5]) % 20

            print("------------------------------------------------------------------------------")
            if (legitimate_trafic / len(y_flow_pred) * 100) > 80:
                print("legitimate traffic ...")
            else:
                print("ddos trafic ...")
                for index, row in df_block.iterrows():
                    ip_src = row['ip_src']
                    ip_dst = row['ip_dst']
                    dp=self.datapaths.get(row['datapath_id'])
                    ofproto=dp.ofproto
                    parser=dp.ofproto_parser
                    match = parser.OFPMatch(eth_type=ether_types.ETH_TYPE_IP,ipv4_src=ip_src,ipv4_dst=ip_dst)
                    inst = [ofparser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions=[])]
                    mod = ofparser.OFPFlowMod(datapath=dp, priority=1000,
                                    idle_timeout=0, hard_timeout=120,
                                    match=match, instructions=inst)
                    dp.send_msg(mod)
                    print("flow mod is added for ip src: {} and ip dst: {}".format(ip_src, ip_dst))

                print("victim is host: h{}".format(victim))


            print("------------------------------------------------------------------------------")

            # with open("PredictFlowStatsfile.csv", mode="w", newline='') as file0:
            #     writer = csv.writer(file0)
            #     writer.writerow(['timestamp', 'datapath_id', 'flow_id', 'ip_src', 'tp_src', 'ip_dst', 'tp_dst', 'ip_proto', 'icmp_code', 'icmp_type',
            #                      'flow_duration_sec', 'flow_duration_nsec', 'idle_timeout', 'hard_timeout', 'flags', 'packet_count', 'byte_count',
            #                      'packet_count_per_second', 'packet_count_per_nsecond', 'byte_count_per_second', 'byte_count_per_nsecond'])

        except Exception as e:
            pass
