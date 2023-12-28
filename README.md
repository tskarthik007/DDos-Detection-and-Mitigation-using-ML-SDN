# DDos-Detection-and-Mitigation-using-ML-SDN
DDoS detection and mitigation using ML in SDN network using RYU controller and ML technique 

Prerequisite:
  1) python 3.8
  2) Ryu controller
  3) Mininet
  4) Sklearn

Step to run:
  1) run ryu-manager controller.py
  2) In a separate terminal run sudo python topo_8_host.py
  3) To generate normal traffic(inside the mininet)
       i) h1 iperf -s
      ii) h3 iperf -c 10.0.0.1 -t 10
  4) To generate attack traffic(inside the mininet)
     in place of h1 we can give any host name and in place 10.0.0.4 we can give any host dst addr 
       i) (TCP SYN attack): h1 timeout 20s hping3 -S -p 80 Target --rand-source --flood 10.0.0.4
      ii) (ICMP attack): h1 timeout 20s hping3 -1 -V -d 120 -w 64 -p 80 --rand-source --flood 10.0.0.4
     iii) (UDP attack): h1 timeout 20s hping3 -2 -V -d 120 -w 64 --rand-source --flood 10.0.0.4

Description of files:

  controller.py: the controller file send flow and stat request every 10s and analysis the data received from the flow stats. It sends the data to pre-trained                       Random Forest model and predicts whether this batch of traffic is malicious or not. If it's malicious it blocks those ip of fixed amount of time.

  switch.py: This is a base file which is inherited by the controller file. This file adds flow rules to datapath if a new packet comes to the controller.
  
  topo_8_host.py: It builds the topology, there are 2 switches and 8 hosts each switch is connected to 4 hosts. 

  RF_model.joblib: The trained model is saved using joblib library and imported in the controller file for prediction. 



  
  
