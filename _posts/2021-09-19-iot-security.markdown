---
layout: single
slug: iot-security
title:  "Securing the Internet of Things (IoT)"
author: Joseph Rossi
date:   2021-09-19 12:00:00 -0400
excerpt: ""
show_date: True
scholar:
    bibliography: IoT_Security
---

## The rise of IoT

Over the past decade, the Internet of Things (IoT) has gone from a start-up buzzword to an integral part of everyday life. The ubiquity of smartphones and relatively low cost of cloud infrastructure have significantly lowered the bar to entry for new and existing businesses to deliver so-called "smart" devices into the hands and homes of consumers. Many of these products integrate with cloud services and barely require any software engineering to get up and running. Don't have a free hand to start the coffee machine while making breakfast? "Alexa, turn on my coffee machine." Reading on the couch while it's getting dark outside? "Alexa, turn on the living-room lamp." Cars, toasters, refrigerators... they're all (not so slowly) joining the IoT.

While IoT devices continue to overtake the home, industrial systems are incorporating IoT systems into their operations to increase manufacturing efficiency, enable smarter facilities management {% cite azure:iot %}, and provide scalable cost-efficient access to once costly services. In medicine, there are products that allow people with diabetes to monitor and manage their own insulin{% cite tandem:diabetes-care %} without incurring the cost of frequent doctor visits. In civil infrastructure management, IoT solutions are starting to enable smart stormwater management{% cite opti:website %}. The International Data Corporation predicts that by 2023, 70% of enterprises will have incorporated IoT computing into their operations {% cite idc:iot-preditions:2019 %}.

With IoT rapidly integrating into every aspect of business and society, it is becoming more essential than ever that these devices are secure from cyberattacks. Nowadays, it is rare to go a week without hearing of a new vulnerability, data leak, or ransomware attack that compromises the data of hundreds or thousands of people. While the risk of personal data being exposed is great enough, the risks become unacceptable when a compromised insulin pump can kill you[^insulin-pump-note], or foreign hackers are looking to gain control of a country's power grid{% cite wired:russian-hackers-power-grid %}. In these extreme examples, the impact of cyberattacks escalate from financial hardships and identity theft to hazards that could inflict instant physical harm on individuals or communities. Developing and deploying safe and secure systems becomes of paramount importance.

## Why isn't it secure by default?

Security on the Internet has historically been an afterthought. The original technology and protocols powering the Internet (ARPANET, UDP, TCP, HTTP, etc) were not developed with security in mind. As more and more people put their personal and financial data online in the 1990s and 2000s, the need for secure communication started taking center stage. Since security was developed as an add-on, businesses had to opt into security, which slowed down its adoption. It's also tricky to do correctly, even for simple web services, and due to Moore's Law, cryptographic algorithms that were once statistically bulletproof are now easily breakable {% cite leurentpeyrin %}. Even today, simple web services attempting to follow modern best practices suffer from security breaches, DDoS, and ransomware.

IoT system have more layers than traditional web services{% cite iotsense:iotlayers %}, and the challenge of running a secure system is compounded by these layers. The layers include everything from small edge devices up through applications that run in the cloud and constantly analyze, make predictions, and control physical aspects of the system. Security vulnerabilities can be exploited in any layer and in real-world systems, often exist within many layers. Adding more complexity, every part of the system has different amounts of computing resources and communicate using different protocols. Edge devices may communicate over Bluetooth LE, Wi-Fi (which itself has dozens of security protocols), Zigbee, etc, while application servers are set up in the cloud, sharing hardware with hundreds of other companies. Securing every layer in these systems becomes a daunting challenge.

## Ok, security is important and tricky to get right. What does the research say?

Research has been primary driver for the advancement of security on the Internet. Perhaps the most important aspect of security culture is the practice of open publication of cryptographic protocols, security architectures, and implementations of security. After such standards are published, other researchers try to break them! So when organizations like the NSA develop and publish cryptography algorithms like SHA1, the research community can poke at it to find weaknesses that malicious actors could exploit. This is not only valuable feedback to the designers, but also alerts industry professionals to move away from these former best practices{% cite leurentpeyrin %}.

Protocol design is still a main focus for many researchers, defining practices that IoT vendors and system designers could adopt for their own networks. For example, Bonetto et al.{% cite bonetto:al %} proposed an architecture that details the different layers of IoT applications and specifically dives into each one, incorporating details such as how security keys are managed, how new edge devices securely join a network, and where to draw the boundaries between different parts of the network to minimize the attack surface. They focus primarily on the protocols used within and between the different application layers; they also factor in the resource-constrained nature of edge devices by introducing a gateway to handle the heavier cryptographic computations between the "constrained" (i.e. isolated) and "unconstrained" networks.

However, with the rise of IoT, the field of security testing is changing. A growing number of researchers are studying and probing software and hardware for vulnerabilities in their implementation. With the proliferation of cheap microprocessors making their way into every electronic device, vulnerabilities in implementations, especially in vendor-provided software that is often taken as-is by product developers, could leave hundreds or thousands of devices vulnerable to exploit. Researchers in Singapore recently found a variety of vulnerability in the Bluetooth stacks of multiple SoCs. Garbelini et al. showed that with cheap commodity hardware, an attacker can exploit vulnerabilities in these chipsets to render the device non-functional{% cite garbelinial %}. Remember, these chips could be in devices that prevent your city's streets from flooding when it rains or control your dose of medication. Crashing these devices could prevent them from functioning properly when they're needed most.

## What kinds of open-source tools are available?

In recent years, the Bluetooth family of protocols (Bluetooth Classic and BLE) has caught the eye of many researchers. As the "things" get smaller and run on smaller batteries, they need to use less power. In response, the industry is turning to low-energy protocols like Bluetooth. Unlike it's Internet predecessors, Bluetooth was designed with security in mind from the beginning {% cite bluesec1.0 %}. The security specification is quite comprehensive, but it's just a specification. Every vendor is on their own to implement to the standard in their chips, which leaves a lot of room for non-compliance and implementation flaws that leave these chips and any products that use them vulnerable to attacks. As researchers uncover these flaws, they are openly releasing the tools they develop to perform the attacks. These tools not only provide an easier starting point for future research, but also serve as tools for vendors to test their security patches or discover vulnerabilities in future versions of their chips.

In 2019, the Secure Mobile Networking (SEEMOO) Lab published the framework InternalBlue. {% cite ClassenJiska2019IJDB %} It appears to be the first of its kind: an open-source framework that turns off-the-shelf Bluetooth devices into sniffers capable of penetration testing. Using InternalBlue, the team at SEEMOO was able to reverse engineer Apple's "MagicPairing" protocol and analyze potential flaws in its design{% cite HeinzeDennis2020 %}. I found the setup to be a bit cumbersome, but it was fairly easy to get running macOS and Raspberry Pi to test out some of the example exploits in the framework.

Inspired by the research using InternalBlue, Garbelini et al. went in a similar direction and reverse engineered the ESP32 Bluetooth stack, to turn a $10 development kit into an active Bluetooth sniffer capable of connecting to and probing Bluetooth vulnerabilities in puppet devices. While the exploit details are still being kept secret until vendors can patch their systems, the firmware for the ESP32 is publically available. I found it easy to set up in less than 30 minutes {% cite garbelinial %}.

IoT security is an important and thriving area of research. As more and more industries adopt IoT, it will become increasingly critical to have mature tools and references for designing, implementing, and validating secure systems. Researchers have developed an open culture, offering powerful tools freely. It's a ripe time to jump in and contribute to keeping people and their data secure.

## Citations

{% bibliography --cited %}

[^insulin-pump-note]: This example in no way reflects that the referenced Tandem product poses any such risk. It's simply to illustrate the risk of insecure IoT medical products. According to the website, t:slim X2 Insulin Pump is being developed in accordance with FDA guidelines.


