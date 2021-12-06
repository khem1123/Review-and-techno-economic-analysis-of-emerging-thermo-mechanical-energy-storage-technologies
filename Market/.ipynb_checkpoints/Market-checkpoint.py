
import pypsa
import pandas as pd
import numpy as np

#%% Create Network!

df_Market=pd.read_csv('data_extra/elspotprice.csv', sep=',', index_col=0,parse_dates=True ) 

# elspotprice.csv is the market price of electricity! 
df_Market['load'] = 1  # load of 1 MW
df_Market['SpotPriceEUR']=df_Market['SpotPriceEUR']*0.82  # convert to USD


#%% Annuity Calculation

# A function for anuity!
def annuity(n,r):
    """Calculate the annuity factor for an asset with lifetime n years and
    discount rate of r, e.g. annuity(20,0.05)*20 = 1.6"""

    if r > 0:
        return r/(1. - 1./(1.+r)**n)
    else:
        return 1/n


#############  Make Network Function !

def ZeroProfit(power=1,energy=2,effi=0.5,factorc=0.33):
    # power= Investment cost power in $/MW_discharge
    # energy = Investment cost Energy in $/MWH 
    # effi = efficiency in fraction 
    # factorc = Cost of charging 1 MW / Investment cost power 1 MW _discharge
    
    network=[]
    network = pypsa.Network()
    network.add("Bus","electricity bus")
    network.set_snapshots(df_Market.index)
    network.add("Load",
                "load",
                bus="electricity bus",
                p_set=df_Market['load'])
    Market = df_Market['SpotPriceEUR'][[hour.strftime("%Y-%m-%dT%H:%M:%SZ") for hour in network.snapshots]]


    #%%  Add A generator (Marketplace)  that cost Market Price to produce

    network.add("Carrier", "marketplace") # in t_CO2/MWh_th


    network.add("Generator",
                "Market",
                bus="electricity bus",
                p_nom_extendable=True,
                carrier="marketplace",
                #p_nom_max=1000,
                capital_cost = 0,
                marginal_cost = Market)


    #%% Add Thermal Storage

    # Data for Thermo Mechanical
    standing_loss=1/100/24  # per hour 
    powerOM=1000
    energyOM=3
    chargeeffi= np.sqrt(effi)
    dischargeeffi= effi/chargeeffi

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
          #max_hours=48*2,
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


    #%% Solve Network
    network.lopf(network.snapshots,
                 solver_name='gurobi',solver_io="python")

    #%% Post Processing

    #    plt.plot(network.loads_t.p['load'][0:96], color='black', label='demand')
    #    plt.plot(network.generators_t.p['Market'][0:96], color='orange', label='From Market')
    #    plt.plot(network.stores_t.p['Tank'][0:96], color='Green', label='Thermal')
    #    plt.grid('True')
    #    plt.legend(fancybox=True, shadow=True, loc='best')
    #    plt.show()
        #%% Total Investment Annualized



    #%% Total Money Made
    Total_Cash= ((network.links_t['p0']['Discharge']*dischargeeffi*Market).sum()-(network.links_t['p0']['Charge']*Market).sum())
    Investment= network.stores.e_nom_opt*energy +network.links.loc['Charge'].p_nom_opt*power*factorc+ network.links.loc['Discharge'].p_nom_opt*dischargeeffi*power*(1-factorc)
    Expenses=network.links['capital_cost']*network.links['p_nom_opt']
    Other= network.stores['capital_cost']*network.stores['e_nom_opt']
    Expenses1=Expenses[0]+Expenses[1]+Other.values
    Profit=(Total_Cash-Expenses1)

    print('Optimum Storage Capacity (MWh) is', network.stores.e_nom_opt)
    print('Optimum Charge Capacity (MWh) is',  network.links.loc['Charge'].p_nom_opt)
    print('Optimum Discharge Capacity (MWh) is',  network.links.loc['Discharge'].p_nom_opt)
    print('Current effic', effi)
    print('Current Capital cost energy', energy)
    print('Current Capital cost power', power)
    print('Total Investment (USD) is', Investment)
    print('Difference in Buying and Selling (Million USD) is =', Total_Cash)
    print('Total profit = ',Profit)

    P=[power,energy,effi,network.stores.e_nom_opt.values, network.links.loc['Charge'].p_nom_opt,network.links.loc['Discharge'].p_nom_opt,Profit,Total_Cash]
    df=pd.DataFrame([P],columns=['power','energy','effi','storage','charge','discharge','profit','Revenew'])

    return Profit/100000, df


#%% While loop continues to increase investment cost power unitil profit is close to zero! 


factorc=0.5  # For a generic storage! 

P=[0,0,0,0,0,0,0,0 ]
B1=pd.DataFrame([P],columns=['power','energy','effi','storage','charge','discharge','profit','Revenew'])

for effi in [0.9,0.7]:
    for energy in [5000,10000,20000,30000,40000,50000,60000,80000,100000,120000]:
        A=100
        cc=10000
        while A>0:
            cc=cc+20000
            B=ZeroProfit(cc, energy, effi,factorc)
            A=B[0]
            B1=B1.append(B[1])


        #%%Use new to increase by 10,000
        cc=cc-20000
        A=100
        while A>0:
            cc=cc+10000
            B=ZeroProfit(cc, energy, effi,factorc)
            A=B[0]
            B1=B1.append(B[1])



        cc=cc-10000
        A=100
        while A>0:
            cc=cc+5000
            B=ZeroProfit(cc, energy, effi,factorc)
            A=B[0]
            B1=B1.append(B[1])



        cc=cc-5000
        A=100
        while A>0:
            cc=cc+1000
            B=ZeroProfit(cc, energy, effi,factorc)
            A=B[0]
            B1=B1.append(B[1])

        cc=cc-1000
        A=100
        while A>0:
            cc=cc+500
            B=ZeroProfit(cc, energy, effi,factorc)
            A=B[0]
            B1=B1.append(B[1])

        cc=cc-500
        A=100
        while A>0:
            cc=cc+100
            B=ZeroProfit(cc, energy, effi,factorc)
            A=B[0]
            B1=B1.append(B[1])

        print('---------------------------------------------------------------------------------------')
        print('------------------------------------Step Complete--------------------------------------')
        print('----------------------------------------------------------------------------------------')

B1.to_csv('Perfect2.csv',index=False)
