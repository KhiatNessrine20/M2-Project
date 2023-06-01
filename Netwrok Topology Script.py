"""Custom topology example

Two directly connected switches plus a host for each switch:

   host --- switch --- switch --- host

Adding the 'topos' dict with a key/value pair to generate our newly defined
topology enables one to pass in '--topo=mytopo' from the command line.
"""

from mininet.topo import Topo
#from mininet.link import TCLink
class MyTopo( Topo ):
  
    def build( self ):
        "Create custom topo."

        # Ajout des Switches et Hotes
        h1 = self.addHost( 'h1' , mac="00:00:00:00:00:01",  ip="10.0.0.1/24") #Attribution de l'adresses Mac & IP  H1
        h2 = self.addHost( 'h2' , mac="00:00:00:00:00:02", ip = "10.0.0.2/24") #Attribution de l'adresses Mac & IP  H2
        s1 = self.addSwitch ('s1')
        s2 = self.addSwitch ('s2')
        s3 = self.addSwitch( 's3' )
        s4 = self.addSwitch( 's4' )
        
        # Ajout des liens
        self.addLink( h1, s1 )
        self.addLink( s1, s2 )
        #self.addLink( s2, s3)
        self.addLink( s1, s3 )
        self.addLink( s2, s4)
        self.addLink( s3, s4)
        self.addLink( s4, h2 )

topos = { 'mytopo': ( lambda: MyTopo() ) }