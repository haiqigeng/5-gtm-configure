___INFO___
{"id":"cvt_meta","displayName":"Synthetic matching fixture","type":"TAG","version":1}

___TEMPLATE_PARAMETERS___
[
  {"type":"CHECKBOX","name":"advancedMatching","checkboxText":"Enable matching"},
  {"type":"SIMPLE_TABLE","name":"advancedMatchingList","simpleTableColumns":[
    {"defaultValue":"","displayName":"Name","name":"name","type":"TEXT"},
    {"defaultValue":"","displayName":"Value","name":"value","type":"TEXT"}
  ]}
]

___SANDBOXED_JS_FOR_WEB_TEMPLATE___
// This source only exercises static installed identity/field binding.
// It sends no event and makes no claim about a Meta implementation.
data.gtmOnSuccess();

___WEB_PERMISSIONS___
[]

___TESTS___
[]
