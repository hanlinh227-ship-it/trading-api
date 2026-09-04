package com.hanlinh.bybitmonitor

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.*
import androidx.compose.ui.graphics.Color
import androidx.lifecycle.viewmodel.compose.viewModel
import com.hanlinh.bybitmonitor.service.MonitorForegroundService
import com.hanlinh.bybitmonitor.ui.MonitorScreen
import com.hanlinh.bybitmonitor.ui.MonitorViewModel

class MainActivity:ComponentActivity(){
    override fun onCreate(savedInstanceState:Bundle?){super.onCreate(savedInstanceState);setContent{val vm:MonitorViewModel=viewModel();val state by vm.state.collectAsState();var bg by remember{mutableStateOf(MonitorForegroundService.isEnabled(this))};val permission=rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()){};LaunchedEffect(Unit){if(Build.VERSION.SDK_INT>=33)permission.launch(Manifest.permission.POST_NOTIFICATIONS)};MaterialTheme(colorScheme=lightColorScheme(primary=Color(0xFF111827),secondary=Color(0xFF2563EB),background=Color(0xFFF5F7FA),surface=Color.White)){MonitorScreen(state,vm::pair,vm::refresh,vm::disconnect,bg){on->bg=on;MonitorForegroundService.setEnabled(this,on)}}}}
}
