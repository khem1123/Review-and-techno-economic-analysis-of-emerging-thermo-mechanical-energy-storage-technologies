import pypsa
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

df_solar = pd.read_csv('data/Solar.csv', sep=',', index_col=0,parse_dates=True, skiprows=3 ) # in MWh
CF_solar=df_solar['electricity']
df_wind = pd.read_csv('data/Wind.csv', sep=',', index_col=0,parse_dates=True, skiprows=3 ) # in MWh
CF_wind=df_wind['electricity']
df_solar['load']=100
load=df_solar['load']

# A function for anuity!
def annuity(n,r):
    """Calculate the annuity factor for an asset with lifetime n years and
    discount rate of r, e.g. annuity(20,0.05)*20 = 1.6"""

    if r > 0:
        return r/(1. - 1./(1.+r)**n)
    else:
        return 1/n


    
def ZeroProfit(x):
    power=x[0]
    energy=x[1]
    effi=x[2]
    network=[]
    
    factorc=0.33
    standing_loss=1/100/24
    powerOM=8000
    energyOM=2.4
    
    dT=0.25
    cT=0.55/0.25
    
    rat=cT/dT
    dischargeeffi=np.sqrt(effi/rat)
    chargeeffi=(effi)/dischargeeffi

    
    network = pypsa.Network()
    network.set_snapshots(df_wind.index)
    network.add("Bus","electricity bus")
    network.add("Load",
                "load", 
                bus="electricity bus", 
                p_set=load)


    # add the different carriers, only gas emits CO2
    network.add("Carrier", "gas") # in t_CO2/MWh_th
    network.add("Carrier", "onshorewind")
    network.add("Carrier", "solar")

    # add onshore wind generator
    capital_cost_onshorewind = annuity(30,0.07)*910000*(1+0.033) # in €/MW
    network.add("Generator",
                "onshorewind",
                bus="electricity bus",
                p_nom_extendable=True,
                carrier="onshorewind",
                #p_nom_max=1000, # maximum capacity can be limited due to environmental constraints
                capital_cost = capital_cost_onshorewind,
                marginal_cost = 0.015,
                p_max_pu = CF_wind)

    # add solar PV generator

    capital_cost_solar = annuity(25,0.07)*425000*(1+0.03) # in €/MW
    network.add("Generator",
                "solar",
                bus="electricity bus",
                p_nom_extendable=True,
                carrier="solar",
                #p_nom_max=1000, # maximum capacity can be limited due to environmental constraints
                capital_cost = capital_cost_solar,
                marginal_cost = 0.02,
                p_max_pu = CF_solar)

    # add OCGT (Open Cycle Gas Turbine) generator
    capital_cost_OCGT = 0 # in €/MW
    fuel_cost = x[3] # in €/MWh_th
    efficiency = 0.33
    marginal_cost_OCGT = fuel_cost # in €/MWh_el
    network.add("Generator",
                "OCGT",
                bus="electricity bus",
                p_nom_extendable=True,
                carrier="gas",
                #p_nom_max=1000,
                capital_cost = capital_cost_OCGT,
                marginal_cost = marginal_cost_OCGT)


    #Create a new carier i.e. storage
    network.add("Carrier",
          "Storage")

    #Create a new bus storage !

    network.add("Bus",
          "Storage",
          carrier = "Storage")

    #Connect the storege to the bus
    network.add("Store",
          "Tank",
          bus = "Storage",
          e_nom_extendable = True,
          standing_loss=standing_loss,
          e_cyclic = True,
          marginal_cost=energyOM,
          capital_cost = annuity(30, 0.07)*energy)

    #Add the link Tank that transport energy from the electricity bus (bus0) to the tank with 98%
    network.add("Link",
          "Charge",
          bus0 = "electricity bus",
          bus1 = "Storage",
          p_nom_extendable = True,
          efficiency = chargeeffi,
          capital_cost =  annuity(30, 0.07)*power*factorc+powerOM*factorc)

    #Add Generator that transports energy from the storage bus to the electricity bus
    #with 38%
    network.add("Link",
          "Discharge",
          bus0 = "Storage",
          bus1 = "electricity bus",
          p_nom_extendable = True,
          efficiency = dischargeeffi,
          capital_cost = annuity(30, 0.07)*dischargeeffi*power*(1-factorc)+powerOM*(1-factorc))

    network.lopf(network.snapshots, 
                 solver_name='gurobi',solver_io="python")
    g=network.generators_t.p['OCGT'].sum()
    s=network.generators_t.p['solar'].sum()
    w=network.generators_t.p['onshorewind'].sum()
    st=network.links_t['p0']['Discharge'].sum()*dischargeeffi 
    c=network.links_t['p0']['Charge'].sum()*chargeeffi
    ww=network.generators.loc['onshorewind'].p_nom_opt
    ss=network.generators.loc['solar'].p_nom_opt

    print('Optimum Storage Capacity (MWh) is', network.stores.e_nom_opt)
    print('Optimum Charge Capacity (MW) is',  network.links.loc['Charge'].p_nom_opt)
    print('Optimum Discharge Capacity (MW) is',  network.links.loc['Discharge'].p_nom_opt)
    print('Total Electricity from Gas is',  network.generators_t.p['OCGT'].sum())
    print('Fuel cost is', fuel_cost)
    print('Current Power cost', power)
    print('Current Storage cost', energy)
    
    Discharge=network.links.loc['Discharge'].p_nom_opt*dischargeeffi
    
    # Save output variables that I want as a panda dataframe. 
    
    P=[power,energy,effi,network.stores.e_nom_opt.values, network.links.loc['Charge'].p_nom_opt,network.links.loc['Discharge'].p_nom_opt*dischargeeffi,fuel_cost,g,s,w,st,c,ww,ss]

    df=pd.DataFrame([P],columns=['power','energy','effi','storage','charge','discharge','fuel_cost','Gasuse','solar','wind','discharge','charge','Wind','Solar'])
    
    
    return st/876, df

################

# This is looping part ! 
# I use brute search; could not do it use Linesearch Algrothim! 


P=[0,0,0,0,0,0,0,0 ,0,0,0,0,0,0]
B1=pd.DataFrame([P],columns=['power','energy','effi','storage','charge','discharge','fuel_cost','Gasuse','solar','wind','discharge','charge','Wind','Solar'])
for fuel_price in [60,100,140]: 
    for effi in [0.45,0.55,0.65]:
        for energy in [5000,10000,20000,30000,40000,50000]:
            A=100
            cc=300000
            while A>20:
                cc=cc+200000
                B=ZeroProfit([cc, energy, effi,fuel_price])
                A=B[0]
                B1=B1.append(B[1])

            cc=cc-200000
            A=100
            while A>20:
                cc=cc+100000
                B=ZeroProfit([cc, energy, effi,fuel_price])
                A=B[0]
                B1=B1.append(B[1])

            cc=cc-100000
            A=100
            while A>20:
                cc=cc+50000
                B=ZeroProfit([cc, energy, effi,fuel_price])
                A=B[0]
                B1=B1.append(B[1])

            cc=cc-50000
            A=100
            while A>20:
                cc=cc+10000
                B=ZeroProfit([cc, energy, effi,fuel_price])
                A=B[0]
                B1=B1.append(B[1])

            cc=cc-10000
            A=100
            while A>20:
                cc=cc+5000
                B=ZeroProfit([cc, energy, effi,fuel_price])
                A=B[0]
                B1=B1.append(B[1])

            cc=cc-5000
            A=100
            while A>20:
                cc=cc+1000
                B=ZeroProfit([cc, energy, effi,fuel_price])
                A=B[0]
                B1=B1.append(B[1])

            print('---------------------------------------------------------------------------------------')
            print('------------------------------------Step Complete--------------------------------------')
            print('----------------------------------------------------------------------------------------')


B1.to_csv('PumpedThermal_Storage.csv',index=False)