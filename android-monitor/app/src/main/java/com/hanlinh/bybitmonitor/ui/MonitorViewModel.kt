package com.hanlinh.bybitmonitor.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.hanlinh.bybitmonitor.data.MonitorRepository
import com.hanlinh.bybitmonitor.model.MonitorSnapshot
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class MonitorUiState(val pairingRequired:Boolean=true,val pairing:Boolean=false,val error:String?=null,val connection:String="DISCONNECTED",val snapshot:MonitorSnapshot?=null)
class MonitorViewModel(app:Application):AndroidViewModel(app){
    private val repo=MonitorRepository(app)
    private val _state=MutableStateFlow(MonitorUiState(pairingRequired=!repo.hasToken()))
    val state:StateFlow<MonitorUiState> = _state.asStateFlow()
    init{if(repo.hasToken())connect()}
    fun pair(code:String,name:String){if(code.isBlank())return;viewModelScope.launch{_state.value=_state.value.copy(pairing=true,error=null);runCatching{repo.pair(code,name)}.onSuccess{_state.value=_state.value.copy(pairingRequired=false,pairing=false,error=null);connect()}.onFailure{_state.value=_state.value.copy(pairing=true,pairingRequired=true,error=it.message?:"PAIR_FAILED").copy(pairing=false)}}}
    fun refresh(){viewModelScope.launch{runCatching{repo.fetchSnapshot()}.onSuccess{_state.value=_state.value.copy(snapshot=it,error=null)}.onFailure{_state.value=_state.value.copy(error=it.message)}}}
    private fun connect(){repo.stopRealtime();viewModelScope.launch{runCatching{repo.fetchSnapshot()}.onSuccess{_state.value=_state.value.copy(pairingRequired=false,snapshot=it,error=null)}};repo.startRealtime({_state.value=_state.value.copy(pairingRequired=false,snapshot=it,error=null)},{_state.value=_state.value.copy(connection=it)})}
    fun disconnect(){repo.clearToken();_state.value=MonitorUiState(pairingRequired=true)}
    override fun onCleared(){repo.stopRealtime();super.onCleared()}
}
