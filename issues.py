# import-issues-to-github
# reads a .csv file (first and only argument) and creates github issues accordingly

#   Overall procedure for creating a new issue:
#   1. Will the issue be tied to a milestone?
#     YES: does a milestone with the specified name already exist in the repo?
#       YES: get the number of that milestone
#       NO: create a new milestone and get its number
#     NO: go to the next step
#   2. create the issue (and tie it to the specified milestone number if any)
#   3. if status starts with DONE or CANCEL, edit the issue to change its state to 'closed',
#      and add a comment with the full status text

# this works to get all issues for repo 'hello-world' belonging to user 'joe':
# curl -H "Authorization: token aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" https://api.github.com/repos/joe/hello-world/issues

# this works to create an issue (must use this quote scheme for Windows)
# curl -H "Authorization: token aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" -d "{ \"title\":\"New logo\"}" https://api.github.com/repos/joe/hello-world/issues


#  Mapping from csv to GitHub issue:
# (see GitHub Issues API docs: https://developer.github.com/v3/issues/#create-an-issue )

#   column name      handling
#   -----------------------------------------
#   Title            'title' field of POST request
#   Body             'body' field of POST request
#   Status           if text begins with 'DONE' then edit the issue after creating
#                      to change state to 'closed', and if there is additional text,
#                      create a comment with full Status text; if 'CANCEL', close
#                      the issue and add a comment with full Status text;
#                      otherwise, if not blank, create a comment with the Status text
#   HelpWanted       if 'yes' then add label 'help wanted', otherwise take no action
#   Category         add a label with the text of the cell value only
#   Milestone        if the milestone already exists, use its number; if not, create it first
#   <anything else>  '<column_name>:<cell_value>' added to 'labels' field of POST request

# example:
#  Status,Category,Milestone,Title,Body
#  ,bug,docs,Make a README,like it says

# 11-13-16  TMG   change to use python requests instead of external dependency on curl

import os
import sys
import csv
import json
import urllib.parse
from config import *
import requests
import time

# readMilestones: return a dictionary of the repo's existing milestones (keys='title',values='number')
def readMilestones():
	d={}
	time.sleep(1) # per GitHub API best practices
	response=requests.get(milestonesUrl,headers=headers)
	if response.status_code!=200:
		print(response.headers)
		print(json.loads(response.text))
	msList=json.loads(response.text)
	for msDict in msList:
# 		pd(msDict)
		for key in msDict:
			d[msDict["title"]]=msDict["number"]
	global pauseCount
	pauseCount+=1
	return d


# createMilestone(title): create a new milestone in the repo with title='title';
#    do not try to return a value; instead, the caller should call readMilestones
#    to refresh the index afterwards
def createMilestone(title):
	time.sleep(1) # per GitHub API best practices
	payload={}
	payload["title"]=title
	response=requests.post(milestonesUrl,data=json.dumps(payload),headers=headers)
	if response.status_code!=201:
		print(response.headers)
		print(json.loads(response.text))
	print("     Created milestone :",title)
	global pauseCount
	pauseCount+=1
	
	
def createComment(n,body):
	time.sleep(1) # per GitHub API best practices
	url=issuesUrl+"/"+str(n)+"/comments"
	payload={}
	payload["body"]=body
	response=requests.post(url,data=json.dumps(payload),headers=headers)
	if response.status_code!=201:
		print(response.headers)
		print(json.loads(response.text))
	print("     Created comment for issue ",str(n),":",body)
	global pauseCount
	pauseCount+=1
	

def closeIssue(n):
	time.sleep(1) # per GitHub API best practices
	url=issuesUrl+"/"+str(n)
	payload={}
	payload["state"]="closed"
	response=requests.patch(url,data=json.dumps(payload),headers=headers)
	if response.status_code!=200:
		print(response.headers)
		print(json.loads(response.text))
	print("     Closed issue :",str(n))
	global pauseCount
	pauseCount+=1
	
	
def createIssue(rowDict):
# 	pd(rowDict)
	d={}
	global msIndex
	labels=[]
	status=""
	for key in rowDict:
		if key=="Title":
			d["title"]=rowDict["Title"]
		elif key=="Body":
			d["body"]=rowDict["Body"]
		elif key=="Status":
			status=rowDict["Status"]
		elif key=="HelpWanted":
			if rowDict["HelpWanted"]=="yes":
				labels.append("help wanted")
		elif key=="Category":
			labels.append(rowDict["Category"])
		elif key=="Milestone":
			msTitle=rowDict["Milestone"]
			if msTitle!="":
				if msTitle not in msIndex:
					createMilestone(msTitle)
					msIndex=readMilestones()
				msNumber=msIndex[msTitle]
# 				print("milestone:",msTitle,":",msNumber)
				d["milestone"]=msNumber	
		else:
			labels.append(key+":"+rowDict[key])
	d["labels"]=labels
# 	jsonString=json.dumps(dict).replace('"',r'\"')
# 	print(jsonString)
	time.sleep(1) # per GitHub API best practices
	response=requests.post(issuesUrl,data=json.dumps(d),headers=headers)
	global pauseCount
	pauseCount+=1
	if response.status_code!=201:
		print(response.headers)
		print(json.loads(response.text))
	rd=json.loads(response.text)
	issueNumber=rd["number"]
	print("   Created issue #"+str(issueNumber)+": "+rd["title"])

	if status != "":
		createComment(issueNumber,status)
	if status.startswith("DONE") or status.startswith("CANCEL"):
		closeIssue(issueNumber)

# if there are double-quote issues:
#		
# #	encoding once doesn't escape double-quotes
# #	jsonString = json.dumps(dictionary)
# 
# #	encoding twice doesn't quite work either: -d "{" becomes -d ""{\"  (extra double quote)
# #	jsonString = json.dumps(json.dumps(dictionary))
# 
# #	instead, encode once then replace all double quotes with backslash-double-quote
# 	jsonString=json.dumps(dictionary).replace('"',r'\"')


def pd(d):
	print("\nPrinting dictionary:")
	for key in d:
		print(key,":",d[key])


def main(args):
	global pauseCount
	filePointer = open(args[1], 'r')
	rows=csv.DictReader(row for row in filePointer if (not row.startswith('#') and row!="\n"))
# 	print("row keys and values:")
	for row in rows:
		if pauseCount>20:
			print(" Pausing for 30 seconds to avoid triggering GitHub abuse detection mechanism...")
			time.sleep(30)
			pauseCount=0
		if row["Title"]!="":
# 			pd(row)
# 			print(str(pauseCount))
			createIssue(row)
	filePointer.close()

pauseCount=0 # simple throttling to avoid GitHub abuse detection mechanism
issuesUrl=githubUrl+"/issues"
milestonesUrl=githubUrl+"/milestones"
headers={"Authorization":"token "+token}
msIndex=readMilestones()

	
if __name__ == "__main__":
	main(sys.argv)
