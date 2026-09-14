package com.hanlinh.androidbrain.protocol

import com.hanlinh.androidbrain.policy.RiskClass

sealed interface Action {
    val riskClass: RiskClass
}

data class LaunchApp(val packageName: String) : Action {
    override val riskClass = RiskClass.A
}

data class ClickNode(val selector: String) : Action {
    override val riskClass = RiskClass.A
}

data class LongClickNode(val selector: String) : Action {
    override val riskClass = RiskClass.A
}

data object ReadScreen : Action {
    override val riskClass = RiskClass.A
}

data class SetText(val selector: String, val value: String) : Action {
    override val riskClass = RiskClass.B
}

data object GlobalBack : Action {
    override val riskClass = RiskClass.A
}

data object GlobalHome : Action {
    override val riskClass = RiskClass.A
}

data class Swipe(val startX: Int, val startY: Int, val endX: Int, val endY: Int, val durationMs: Long = 300) : Action {
    override val riskClass = RiskClass.A
}

data class OpenUrl(val url: String) : Action {
    override val riskClass = RiskClass.A
}

data class SendMessage(val contact: String, val message: String) : Action {
    override val riskClass = RiskClass.B
}

data class DeleteData(val itemCount: Int) : Action {
    override val riskClass = RiskClass.C
}

data class WalletSign(val payload: String) : Action {
    override val riskClass = RiskClass.D
}
