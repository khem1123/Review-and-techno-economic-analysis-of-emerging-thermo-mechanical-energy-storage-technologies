import pypsa
import pandas as pd
import matplotlib.pyplot as plt

# CF for wind, Solar and 100 MW flat load 
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

    
def ZeroProfit(power=300000,energy=200000,effi=0.9, fuel_cost=100):

    network=[]
    
    # Data for Specific technology (Molten Salt here!)
    factorc=0.097  # I supply total capital cost for Power (charging (1 MW ele)+ discharging (1 MW ele)).  I use this to seperate charging & discharging costs
    standing_loss=0.5/100/24
    powerOM=10*1000
    energyOM=3.5
    chargeeffi= 0.98
    dischargeeffi= effi/chargeeffi
    capitalcost_charge= power*factorc+powerOM*factorc      # Charge power per MW_charging
    capitalcost_discharge =power*(1-factorc)+powerOM*(1-factorc) # Pypsa needs cost at start of the node!   
    power2= capitalcost_charge/effi+capitalcost_discharge  # This is how power cost is normally given for 1 MW discharge! 
    life=30
    discount=0.07
    
    
    network = pypsa.Network()
    network.set_snapshots(df_wind.index)
    network.add("Bus","electricity bus")
    network.add("Load",
                "load", 
                bus="electricity bus", 
                p_set=load)


    # add the different carriers
    network.add("Carrier", "gas") 
    network.add("Carrier", "onshorewind")
    network.add("Carrier", "solar")

    # add onshore wind generator
    capital_cost_onshorewind = annuity(30,discount)*910000*(1+0.033) # in €/MW
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
    
    capital_cost_solar = annuity(25,discount)*425000*(1+0.03) # in €/MW
    network.add("Generator",
                "solar",
                bus="electricity bus",
                p_nom_extendable=True,
                carrier="solar",
                #p_nom_max=1000, # maximum capacity can be limited due to environmental constraints
                capital_cost = capital_cost_solar,
                marginal_cost = 0.02,
                p_max_pu = CF_solar)

    # add OCGT (Open Cycle Gas Turbine) generator This one runs with fuel cost and 0 capital cost! 
    capital_cost_OCGT = 0 # in €/MW
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

    #Connect the storage to the bus
    network.add("Store",
          "Tank",
          bus = "Storage",
          e_nom_extendable = True,
          standing_loss=standing_loss,
          e_cyclic = True,
          marginal_cost=energyOM,
          capital_cost = annuity(life, discount)*energy)

    #Add the link Tank that transport energy from the electricity bus (bus0) to the tank with 98%
    network.add("Link",
          "Charge",
          bus0 = "electricity bus",
          bus1 = "Storage",
          p_nom_extendable = True,
          efficiency = chargeeffi,
          capital_cost =  annuity(life, discount)*capitalcost_charge)

    #Add Generator that transports energy from the storage bus to the electricity bus
    #with 38%
    network.add("Link",
          "Discharge",
          bus0 = "Storage",
          bus1 = "electricity bus",
          p_nom_extendable = True,
          efficiency = dischargeeffi,
          capital_cost = annuity(life, discount)*capitalcost_discharge*dischargeeffi)
    # Pypsa gives discharge at start of the link not end. So I have to use factor of discharge efficiency in cost data! 
    


    
    # Make network and save few Parameters 
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
for fuel_cost in [60,100,140]:  
    for effi in [0.38,0.42,0.47]:
        for energy in [5000,10000,20000,30000,40000,50000]:
            A=101
            cc=30000  # Start value for Capital cost ! 
            while A>100:
                cc=cc+200000
                B=ZeroProfit(power=cc, energy=energy, effi=effi,fuel_cost=fuel_cost)
                A=B[0]
                B1=B1.append(B[1])

            cc=cc-200000
            A=101
            while A>100:
                cc=cc+100000
                B=ZeroProfit(power=cc, energy=energy, effi=effi,fuel_cost=fuel_cost)
                A=B[0]
                B1=B1.append(B[1])

            cc=cc-100000
            A=101
            while A>100:
                cc=cc+50000
                B=ZeroProfit(power=cc, energy=energy, effi=effi,fuel_cost=fuel_cost)
                A=B[0]
                B1=B1.append(B[1])

            cc=cc-50000
            A=101
            while A>100:
                cc=cc+10000
                B=ZeroProfit(power=cc, energy=energy, effi=effi,fuel_cost=fuel_cost)
                A=B[0]
                B1=B1.append(B[1])

            cc=cc-10000
            A=101
            while A>100:
                cc=cc+5000
                B=ZeroProfit(power=cc, energy=energy, effi=effi,fuel_cost=fuel_cost)
                A=B[0]
                B1=B1.append(B[1])

            cc=cc-5000
            A=101
            while A>100:
                cc=cc+1000
                B=ZeroProfit(power=cc, energy=energy, effi=effi,fuel_cost=fuel_cost)
                A=B[0]
                B1=B1.append(B[1])

            print('---------------------------------------------------------------------------------------')
            print('------------------------------------Step Complete--------------------------------------')
            print('----------------------------------------------------------------------------------------')


B1.to_csv('Thermal_Storage.csv',index=False)